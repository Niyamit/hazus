# DOGAMI ArcGIS Python Script Alternative to the Hazus-MH Flood Model for User-Defined Facilities
#
# This script is published as part of Oregon Department of Geology and Mineral Industries Open-File Report OFR O-18-04,
# and has an accompanying User Guide and Depth-Damage Function library.
# CITATION TITLE: Open-File Report O-18-04, ArcGIS Python Script Alternative to the Hazus-MH Flood Model for User-Defined Facilities
# CITATION ORIGINATOR:  John M. Bauer, Oregon Department of Geology and Mineral Industries,
# 800 NE Oregon Street, Suite 965, Portland, OR 97232
# Downloadable at  http://www.oregongeology.org/pubs/ofr/p-O-18-04.htm
# 
#Description:
# Intended as a complement to the Hazus-MH Flood model. By using the Depth Damage Functions (DDF)
# exported from Hazus (methods described elsewhere), we calculate the damage calculations entirely outside
# of Hazus. Basic flow:
#	For each flood depth grid specified by the user:
#		Determine depth of flooding at the UDF point.
#		Process, record-by-record:
#			building/content/inventory damage based on the adjusted flood depth, the type of building, using the look-up tables.
# 			Using the building loss ratio, calculates debris and building repair time.
#
#
# Script is intended for users with 'many' flood depth grids generated independently of Hazus-MH Flood,
# and a Hazus-compatible UDF pointfile. Please credit DOGAMI if code is used in whole or in part.
#
# The script's version number is decoupled from the Hazus-MH release version.
#
# The script requires two look-up libraries each, for Building, Content, and Inventory:
# 	* One for the default situation, where the user supplies OccupancyClass, FoundationType, and NumStories but not a DDF ID
#	* One for the full library, where the user has some very specific DDF they wish to employ.
#
# Note this script does not replace all of Hazus-MH Flood functionality - it only replaces the UDF-based estimate.
#
#
# Revision History
#	20160502 v1.0 Initial Version
#	20160720 v2.0 Support for Content added. Support for user-supplied DDFs for Building and Content added.
#			Support for Coastal flooding added.
#	20160823 v2.1  Changed the inputs to be interactive. User specifies the pathnames, etc. Can be GUI'd
#			into an ArcToolBox.
#	20170331 v3.0  Extensive modification to structure, to conform to more maintainable coding styles,
#			based expert feedback:
#				Use Hazus convention for parameter Input/Output names.
# 				Added support for ArcToolBox so that the DDF library is at a default location and not hard-coded.
#			Fixed a Content Loss computation bug when user supplied their own Content Loss.
#			Added support for calculating Inventory Loss (and uncovered Hazus implementation bug).
#	20170630 v3.1
#		Debris support added.
#		Blanks for user-supplied DDFIDs are supported - they are treated as Null, and default DDFs are used
#		Enhancements for sensitivity tests.
#			Depth-in-Struc is set to Null when the structure is not exposed (versus -9999)
#			Added attribute "GridName" which specifies the gridname with each record.
#				Useful for multiple result files withappend/summary stats.
#				Results geodatabase has a time stamp embedded at the end of its name "-HHMM" (hour/minute).
#		Direct Economic Loss support added:
#			Time to full functionality - a Minimum and Maximum value (in days) are provided.
#	20171215 v3.2
#		Attribute name updates to conform to Hazus naming standards in anticipation of formal publication.
#		Added a flood depth grid attribute. Appears redundant, but useful when merging multiple
#			flood depth grids and performing pivot tables/summaries.
#		Added ContentCostUSD InventoryCostUSD output attributes.
#		Released as part of DOGAMI Open-File Report O-18-04.
# ---------------------------------------------------------------------------

# Variations between systems; some import these by default, others don't. Be explicit.
import os,csv,arcpy,sys,time,math,traceback,shutil,datetime

# Overwrite existing outputs if there. Not likely, given the output file gdb naming convention.
arcpy.env.overwriteOutput = True

# Spatial Analyst Checkout. Check it back in at the end.
if arcpy.CheckExtension("Spatial") == "Available":
	arcpy.AddMessage("Checking out Spatial Analyst Extension")
	arcpy.CheckOutExtension("Spatial")
	from arcpy import env
	from arcpy.sa import *
else:
	arcpy.AddError("Unable to get spatial analyst extension")
	arcpy.AddMessage(arcpy.GetMessages(0))
	sys.exit(2)

#########################################################################################################
# Main function. Five parameters See end for main procedure.
#########################################################################################################

def flood_damage(UDFOrig, LUT_Dir, ResultsDir, DepthGrids, QC_Warning):
	# UDFOrig = USer-supplied UDF input file. Full pathname required
	# LUT_Dir = folder name where the Lookup table libraries reside
	# ResultsDir = Where the output file geodatabase will be created. Folder (dir) must exist, else fail
	# DepthGrids = one or more flood depth grids
	# QC_Warning = Boolean, report on informative inconsistency observations if selected, otherwise suppress them

	try:
		arcpy.AddMessage("DOGAMI Hazus Flood UDF loss estimation script, version 3.2, using Flood DDFs from Hazus-MH 4.0")
		# ArcToolBox quirk with a Boolean expression. Argument is passed as a true/false string. Convert to a Boolean
		QC_Warning = QC_Warning.lower() == 'true'
		arcpy.AddMessage("Quality Control Warning Settings set to " +str(QC_Warning))
		# Measure script performance
		start_time = time.time()

		#########################################################################################################
		# UDF Input Attributes. The following are standard Hazus names/capitalizations.
		#########################################################################################################
		UserDefinedFltyId		= "UserDefinedFltyId"   # Name change example:  UserDefinedFltyId = "UDFID"
		OccupancyClass			= "OccupancyClass"
		Cost					= "Cost"
		ContentCost				= "ContentCost"
		Area					= "Area"
		NumStories				= "NumStories"
		FoundationType			= "FoundationType"
		FirstFloorHt			= "FirstFloorHt"
		BldgDamageFnID			= "BldgDamageFnID"  # Yes, a capitalization quirk. We retain the Hazus convention.
		ContDamageFnId			= "ContDamageFnId"
		InvDamageFnId			= "InvDamageFnId"
		# Note there is no Hazus or CDMS equivalent for the following two input variables - see User Guide
		InvCost					= "InvCost"
		flC						= "flC"

		# If your UDF Naming Convention differs from the Hazus namings,
		# you can specify your names here, and override the assignments above
		# Example: (of course, uncomment this)
		# UserDefinedFltyId = "UDF_ID"

		# Note that this script has no use for the following Hazus-MH Flood UDF variables:
		#	Name, Address, City, Statea, Zipcode, Contact, PhoneNumber, YearBuilt, BackupPower,
		#	ShelterCapacity, Latitude, Longitude, Comment, BldgType, DesignLevel, FloodProtection

		#########################################################################################################
		#  UDF Output Attributes
		#########################################################################################################
		# Good programming practice: have these names as variables rather than hardcoded within commands
		# Most users need not change these, unless you do not like the names
		BldgDmgPct				= "BldgDmgPct"
		BldgLossUSD				= "BldgLossUSD"
		ContentCostUSD			= "ContentCostUSD"
		ContDmgPct				= "ContDmgPct"
		ContentLossUSD			= "ContentLossUSD"
		InventoryCostUSD		= "InventoryCostUSD"
		InvDmgPct				= "InvDmgPct"
		InventoryLossUSD 		= "InventoryLossUSD"

		# Note there are no Hazus equivalents for the following output attributes.
		# DOGAMI believes these to be value-added, and suggests Hazus provide this information.
		# See spreadsheet accompanying the script for naming convention
		flExp 		= "flExp"
		Depth_in_Struc	= "Depth_in_Struc"
		Depth_Grid	= "Depth_Grid"    # The renamed raster sample data. "RASTERVALU" is not a useful name
		SOID		= "SOID"		# Specific Occupancy ID
		BDDF_ID		= "BDDF_ID"
		CDDF_ID		= "CDDF_ID"
		IDDF_ID		= "IDDF_ID"
		DebrisID	= "DebrisID"
		Debris_Fin	= "Debris_Fin"  	# Debris for Finish work
		Debris_Struc= "Debris_Struc"  	# Debris from structural elements
		Debris_Found= "Debris_Found"   	# Debris from foundation
		Debris_Tot	= "Debris_Tot"      # Total Debris - sum of the previous
		GridName	= "GridName"
		Restor_Days_Min	= "Restor_Days_Min" # Repair/Restoration times
		Restor_Days_Max	= "Restor_Days_Max"

		#########################################################################################################
		#  Setups for other namings.
		#########################################################################################################
		# Building, Content, Inventory DDF Lookup tables. Use these if user does not supply their own DDF_ID
		# Note that Inventory has no unique LUTs for Coastal Zones.
		# Prefix Naming Convention in this program:
		#   B   Building
		#   C   Content
		#   I   Inventory
		BR	  	= "Building_DDF_Riverine_LUT_Hazus4p0.csv"
		BCA	 	= "Building_DDF_CoastalA_LUT_Hazus4p0.csv"
		BCV	 	= "Building_DDF_CoastalV_LUT_Hazus4p0.csv"
		BFull	= "flBldgStructDmgFn.csv"	# Full DDF library for Building Structural damage

		CR	  	= "Content_DDF_Riverine_LUT_Hazus4p0.csv"
		CCA	 	= "Content_DDF_CoastalA_LUT_Hazus4p0.csv"
		CCV	 	= "Content_DDF_CoastalV_LUT_Hazus4p0.csv"
		CFull	= "flBldgContDmgFn.csv"	# Full DDF library for Building Content damage

		IR	  	= "Inventory_DDF_LUT_Hazus4p0.csv"
		IFull	= "flBldgInvDmgFn.csv"	# Full DDF library for Building Inventory damage
		IEconParams	= "flBldgEconParamSalesAndInv.csv"  # Needed to calculate business inventory value and loss
		DebrisX	= "flDebris_LUT.csv"	# A synthesis of [dbo].[flDebris] and information Hazus Flood Technical Manual (2011), Table 11.1
		RestFnc	= "flRsFnGBS_LUT.csv"	# A modification of [db].[flRsFnGBS] to make it compatible for lookup table purposes

		# Other Lookup tables exported from SQL database that may be of interest for Direct Economic Loss calculations.
		# The basic need DOGAMI had was to establish the building restoration times -
		# and that is fundamental information for all other direct economic loss calculations
		# DOGAMI did not calculate, for example, rental income loss.
		# You can expand the functionality, if you wish,
		# following the methods outlined in the Hazus Flood Technical Manual (2011)
		#xx = "flBldgEconParamWageCapitalIncome.csv"
		#xx = "flBldgEconParamRental.csv"
		#xx = "flBldgEconParamRecaptureFactors.csv"
		#xx = "flBldgEconParamOwnerOccupied.csv"

		# Process some of the user input.
		UDFRoot	 = os.path.basename(UDFOrig)
		ts = ('{:%Y%m%d-%H%M}'.format(datetime.datetime.now()))  # Date Stamp for the file gdb name
		x = UDFRoot +"_Results_" + ts
		y = x + ".gdb"
		z = os.path.join(ResultsDir,y)
		if arcpy.Exists(z):
			arcpy.AddMessage("Note that an existing fgdb already exists; we are deleting that and creating a new fgdb")
			arcpy.AddMessage("   "+ z)
			arcpy.Delete_management(z)
		arcpy.CreateFileGDB_management(ResultsDir,x)
		Resultsfgdb = os.path.join(ResultsDir,y)
		arcpy.AddMessage("Results geodatabase: " + Resultsfgdb)

		# Set up the look-up tables
		BRP  = os.path.join(LUT_Dir, BR)
		BCAP = os.path.join(LUT_Dir, BCA)
		BCVP = os.path.join(LUT_Dir, BCV)
		BFP  = os.path.join(LUT_Dir, BFull)
		CRP  = os.path.join(LUT_Dir, CR)
		CCAP = os.path.join(LUT_Dir, CCA)
		CCVP = os.path.join(LUT_Dir, CCV)
		CFP  = os.path.join(LUT_Dir, CFull)
		IRP  = os.path.join(LUT_Dir, IR)
		IFP  = os.path.join(LUT_Dir, IFull)
		IEP  = os.path.join(LUT_Dir, IEconParams)
		Debris = os.path.join(LUT_Dir,DebrisX)
		Rest = os.path.join(LUT_Dir,RestFnc)

		# Process the look-up tables into a list of Dictionary elements
		# Note the standard (default) Lookup Tables were separately developed.
		# Yes, they are a subset of the full lookup table
		bddf_lut_riverine 	= [row for row in csv.DictReader(open(BRP))]
		bddf_lut_coastalA 	= [row for row in csv.DictReader(open(BCAP))]
		bddf_lut_coastalV 	= [row for row in csv.DictReader(open(BCVP))]
		bddf_lut_full	 	= [row for row in csv.DictReader(open(BFP))]

		cddf_lut_riverine 	= [row for row in csv.DictReader(open(CRP))]
		cddf_lut_coastalA 	= [row for row in csv.DictReader(open(CCAP))]
		cddf_lut_coastalV 	= [row for row in csv.DictReader(open(CCVP))]
		cddf_lut_full	 	= [row for row in csv.DictReader(open(CFP))]

		iddf_lut_riverine 	= [row for row in csv.DictReader(open(IRP))]
		iddf_lut_full	 	= [row for row in csv.DictReader(open(IFP))]
		iecon_lut			= [row for row in csv.DictReader(open(IEP))]

		debris_lut			= [row for row in csv.DictReader(open(Debris))]
		rest_lut			= [row for row in csv.DictReader(open(Rest))]

		# Build up lists to use for checking legitimate user-supplied DDF_ID values
		bddf_lut_full_list = []
		cddf_lut_full_list = []
		iddf_lut_full_list = []
		for x in bddf_lut_full:
			bddf_lut_full_list.append(x['BldgDmgFnID'])    # Yes, the capitalization is due to a quirk in the [dbo].[flBldgStructDmgFn].
		for x in cddf_lut_full:
			cddf_lut_full_list.append(x['ContDmgFnId'])  # Yes, the case is inconsistent with Building column name. That's the way the Hazus database is.
		for x in iddf_lut_full:
			iddf_lut_full_list.append(x['InvDmgFnId'])

		Content_x_0p5 = ['RES1','RES2','RES3A','RES3B','RES3C','RES3D','RES3E','RES3F','RES4','RES5','RES6','COM10']
		Content_x_1p0 = ['COM1','COM2','COM3','COM4','COM5','COM8','COM9','IND6','AGR1','REL1','GOV1','EDU1']
		Content_x_1p5 = ['COM6','COM7','IND1','IND2','IND3','IND4','IND5','GOV2','EDU2']

		# Default inventory DDF only defined for a subset. IF not in this set, set default Inventory Cost Basis = 0
		Inventory_List = ['COM1','COM2','IND1','IND2','IND3','IND4','IND5','IND6','AGR1']

		# Check for the presence of optional fields (Coastal Flooding, user-supplied DDFs for Building, Content, Inventory)
		#
		CoastalZoneSupplied = ubddf = ucddf = uiddf =  cdest = idest = CoastalZoneCode = uccost = uicost = 0
		xt = arcpy.ListFields(UDFOrig,flC)
		if len(xt):
			arcpy.AddMessage( "Coastal Flooding attribute (flC) supplied. Will use where specified")
			CoastalZoneSupplied = 1

		xt = arcpy.ListFields(UDFOrig,BldgDamageFnID)
		if len(xt):
			arcpy.AddMessage( "User-supplied Building Depth Damage Function (BldgDamageFnID) attribute supplied. Will use where specified")
			ubddf = 1

		xt = arcpy.ListFields(UDFOrig,ContDamageFnId)
		if len(xt):
			arcpy.AddMessage("User-supplied Content  Depth Damage Function attribute (ContDamageFnId supplied. Will use where specified")
			ucddf = 1

		xt = arcpy.ListFields(UDFOrig,InvDamageFnId)
		if len(xt):
			arcpy.AddMessage("User-supplied Inventory Depth Damage Function attribute (InvDamageFnId supplied. Will use where specified")
			uiddf = 1

		xt = arcpy.ListFields(UDFOrig,ContentCost)
		if len(xt):
			arcpy.AddMessage( "User-supplied Content Cost supplied.  Will use user supplied value where specified, else use the default")
			uccost = 1

		xt = arcpy.ListFields(UDFOrig,InvCost)
		if len(xt):
			arcpy.AddMessage("User-supplied Inventory Cost supplied.  Will use user supplied value where specified, else use the default")
			uicost = 1

		# Process each depth grid specified by user
		DGrids = DepthGrids.split(';')   # Using the interactive window, it's not a list. Make it so.
		for dgp in DGrids:
			arcpy.AddMessage(" ")    # A formatting step to improve readability of output)
			arcpy.AddMessage( "Querying depth grid " + dgp)

			# Set up the Results file. Extract grid to points, add needed fields, adjust for First Floor Height.
			# Depth_in_Struc:  The adjusted flood depth
			# flExp:   A simple 1/0 statement: is the UDF in the specified floodplain or is it not?
			# SOID = SpecificOccupId.  A conversion of the OccupancyClass, FoundationType, and NumStories fields into a 4 to 5 character string for lookup.
			# BDDF_ID = the particular Depth Damage Function ID used for that record
			# BldgDmgPct = Loss Ratio for Building
			# BldgLossUSD = Estimated Building Loss in US$  (some fraction of the user-specified Cost)
			#
			# Need to strip out any periods in the depth grid file name, say, "depth100.tif", as periods are COMPLETELY UNACCEPTABLE in fgdb feature class naming
			# And if an input shapefile is specified, drop the *.shp extension. So a Texas Two Step to get a clean name
			y = os.path.split(dgp)[1]
			x = UDFRoot.split('.')[0] + "_" + y.split('.')[0]
			ResultsFile = os.path.join(Resultsfgdb,x)
			arcpy.AddMessage("Writing results to " + ResultsFile)
			gridroot = y    #  Put into an attribute in the Results file. Redundant, but handy when appending multiple results files together.

			# Some research should go into INTERPOLATE versus NONE in the next function.
			# A cursory peek suggested Hazus-MH Flood does 'NONE' (it had a better match).
			# So to better match to the Hazus-MH Flood results, we (for now) choose 'NONE'.
			ExtractValuesToPoints(UDFOrig, dgp, ResultsFile, "NONE", "VALUE_ONLY")
			# Change name of the generic RASTERVALU to Depth_Grid
			arcpy.AlterField_management(ResultsFile,"RASTERVALU",Depth_Grid,Depth_Grid)

			# Add the needed fields. Format of command came from ArcGIS "Copy as snippet", so has excess verbiage which could probably be tossed.
			arcpy.AddField_management(in_table=ResultsFile,field_name=Depth_in_Struc, 	field_type="FLOAT", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=flExp,	 		field_type="SHORT", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=SOID,				field_type="TEXT", field_precision="", field_scale="", field_length="5", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=BDDF_ID,			field_type="TEXT", field_precision="", field_scale="", field_length="6", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=BldgDmgPct,		field_type="FLOAT", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=BldgLossUSD,		field_type="LONG", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=ContentCostUSD,	field_type="LONG", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=CDDF_ID,			field_type="TEXT", field_precision="", field_scale="", field_length="6", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=ContDmgPct,		field_type="FLOAT", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=ContentLossUSD,	field_type="LONG", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=InventoryCostUSD,	field_type="LONG", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=IDDF_ID,			field_type="TEXT", field_precision="", field_scale="", field_length="6", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=InvDmgPct,		field_type="FLOAT", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=InventoryLossUSD,	field_type="LONG", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=DebrisID,			field_type="TEXT", field_precision="", field_scale="", field_length="12", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=Debris_Fin,		field_type="LONG", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=Debris_Struc,		field_type="LONG", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=Debris_Found,		field_type="LONG", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=Debris_Tot,		field_type="LONG", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=Restor_Days_Min,	field_type="SHORT", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=Restor_Days_Max,	field_type="SHORT", field_precision="", field_scale="", field_length="", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")
			arcpy.AddField_management(in_table=ResultsFile,field_name=GridName,			field_type="Text", field_precision="", field_scale="", field_length="70", field_alias="", field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED", field_domain="")

			# Process each UDF record, calculating its damage based on depth and building type.
			arcpy.AddMessage("Processing depth grid "+ dgp +  " record by record")
			cursor = arcpy.UpdateCursor(ResultsFile)
			counter = 0
			for row in cursor:
				counter += 1
				if counter % 10000 == 0 and QC_Warning:
					arcpy.AddMessage( "   processing record " + str(counter))

				###################################################
				# Depth Adjustments
	   			###################################################
				# Adjust Depth-in-Structure, given the First Floor Height. This will produce the occasional negative value. That is OK
				# NOTE: Some users suggest that Coastal Flooding should be adjusted by an additional 1.0 foot, because in coastal flooding,
				# FFH should be considered to be at the freeboard.
				# However, we confirmed with the Hazus coding team that the Hazus-MH Flood model does NO such adjustment
				# So for now, we do not do ANY FFH adjustment
				#
				# Note this simple calculation varies with the Hazus-MH flood model implementation that rounds FFH to the nearest 0.5 foot level
				# (which will produce minor differences in the loss ratio calculation).
				# We maintain the script implements the methods more cleanly. There was no compelling technical reason for
				# the Hazus-MH flood model to round to the nearest 0.5 foot.
				rastervalue = row.getValue(Depth_Grid)
				FFHeight = row.getValue(FirstFloorHt)
				depth = rastervalue - FFHeight if rastervalue is not None else None   # Must mind the empty (null) case where the UDF has no Raster values
				userDefinedFltyId = row.getValue(UserDefinedFltyId)   # Capture it for reporting purposes when encountering records with odd values.

				# Get some basic information for the record
				# One could insert some quality checks here and revert to a default if an illegal OccupancyClass, FoundationType, or NumStories
				# At minimum, clean up the Occupancy Class. This sometimes has trailing spaces, due to Hazus processing quirks.
				x				= row.getValue(OccupancyClass)
				OC				= x.strip()
				x 				= row.getValue(FoundationType)
				foundationType  = x.strip()
				numStories 		= row.getValue(NumStories)
				area 			= row.getValue(Area)    # Used in Inventory Loss Calculation
				if CoastalZoneSupplied:
					CoastalZoneCode = row.getValue(flC) # Only acquire if a Coastal Zone is defined for that UDF
					CoastalZoneCode = "" if CoastalZoneCode is None else CoastalZoneCode.strip()

				# Build up the SpecifOccupId based on OccupancyClass,NumStories,FoundationType:
				# Prefix, Middle Character, Suffix
				#
				# Prefix: Take advantage of the Slice feature in Python. Note the negative sign for right() equivalent
				# Note that REL1 is the exception in the OccupancyClass list.
				# QC:  We may want to bark an exception here: check for illegal OccupancyClass? or other combos (e.g. RES2 with more than one story)
				sopre = OC[:1]+OC[-(len(OC)-3):] if OC != 'REL1' else 'RE1'

				# Suffix: Easy - Basement or no Basement
				sosuf = 'B' if foundationType == '4' else 'N'

				# Middle Character: Number of Stories
				if OC[:4] == 'RES3':
					# RES3 has three categories: 1 3 5
					somid = '5' if numStories > 4 else '3' if numStories > 2 else '1'

				elif OC[:4] == 'RES1':
					# If NumStories is not an integer, assume Split Level residence
					# Also, cap it at 3.
					numStories = 3 if numStories > 3 else numStories
					somid = str(numStories) if numStories - int(numStories) == 0 else 'S'

				elif OC[:4] == 'RES2':
					# Manuf. Housing is by definition limited to one story
					somid = '1'

				else:
					# All other cases: Easy!  1-3, 4-7, 8+
					somid = 'H' if numStories > 6 else 'M' if numStories > 3 else 'L'

				SpecificOccupId = sopre + somid + sosuf
				row.setValue(SOID,SpecificOccupId)

				# Content and Inventory Cost. Determine each, even if structure not exposed to flooding
				# Content Loss in US$: depends if user supplied a content cost field, and if it is > 0.
				# If not, then use a default multiplier, depending on OccupancyClass, per Hazus-MH Flood Technical Manual table
				CMult =  0.5 if OC in Content_x_0p5 else 1.0 if OC in Content_x_1p0 else 1.5 if OC in Content_x_1p5 else 0
				if uccost:
					xt = row.getValue(ContentCost)
					xt = -1 if xt is None else xt	 # Null value check. If ContentCost is NULL,use the default value
				else:
					xt = -1
				ccost = row.getValue(Cost) * CMult if xt == -1 else xt

				# Inventory Cost
				OWDI = OC in Inventory_List
				xt = row.getValue(InvCost) if uicost else -1
				xt = xt if xt is not None else -1   #  Clean up case where InvCost is supplied but is null
				if OWDI and xt == -1:
					# Use default cost formula
					for lutrow in iecon_lut:
						if lutrow['Occupancy'] == OC:
							GrossSales = lutrow['AnnualSalesPerSqFt']
							BusinessInv = lutrow['BusinessInvPctofSales']
							# Table imports as string type (?!) so we must convert tabular data to a float type
							# Yes, raw data is typically in Integer format, be flexible for future data which may be available in dollars.cents
							# Must divide by 100, as BusinessInv in the input table is a Percent figure
							# Area is in Square Feet
							icost = float(GrossSales)*float(BusinessInv)*area/100
							break
				# If a user-supplied Inventory Cost is supplied, use it.
				elif xt > -1 :
					icost = row.getValue(InvCost)
				else:
					icost =0

				row.setValue(ContentCostUSD,ccost)
				row.setValue(InventoryCostUSD,icost)

				# If no depth measured for that point, set some default values for the output to clearly indicate that there is No Exposure
				# and quickly move on to the next record
				if depth is None or depth < -500:	# Depending on Depth Grid format, the Extract_2_Point returns Null or -9999
					row.setValue(flExp,0)	# Structure is NOT exposed.
					row.setValue(Depth_in_Struc,None)	# Default value, again emphasizing the point is not exposed. Make SummaryStats more straightforward
					row.setValue(BDDF_ID,0)
					row.setValue(BldgDmgPct,0)
					row.setValue(BldgLossUSD,0)
					row.setValue(CDDF_ID,0)
					row.setValue(ContDmgPct,0)
					row.setValue(ContentLossUSD,0)
					row.setValue(IDDF_ID,0)
					row.setValue(InvDmgPct,0)
					row.setValue(InventoryLossUSD,0)
					row.setValue(DebrisID,'')
					row.setValue(Debris_Fin,None) # Partition the Debris into its three components - Table 11.1 Hazus-MH Flood Technical Manual
					row.setValue(Debris_Struc,None)
					row.setValue(Debris_Found,None)
					row.setValue(Debris_Tot,None)
					row.setValue(Restor_Days_Min,0)
					row.setValue(Restor_Days_Max,0)
				else:
					# The UDF is exposed. Calculate Building, Content, Inventory Losses
					row.setValue(flExp,1)
					row.setValue(Depth_in_Struc, depth)  # Record the depth in structure.
					# (To be considered: optional freeboard adjustment for Coastal Flooding)
					# Hazus 4.0 model does *no* adjustment. Some have suggested that one should add a freeboard margin; e.g., adjust FFH by -1 foot.
					# But there is no clear consensus on such a conservative adjustment.

					# If depth is over 24 feet or less than -4 feet, then adjust depth. LUTs do not extend beyond that range!
					# Note that Hazus-MH flood model caps the grid raster at 24 feet, then does the subtraction. This creates some differences in results.
					# We believe that you do the FFH subtraction before capping the depth at 24 feet.
					depth = 24 if depth > 24 else depth
					depth = -4 if depth < -4 else depth

					# Get some basic information for the record
					# One could insert some quality checks here andrevert to a default if an illegal OccupancyClass, FoundationType, or NumStories
					# At minimum, clean up the Occupancy Class. This sometimes has trailing spaces, due to Hazus processing quirks.
					x				= row.getValue(OccupancyClass)
					OC				= x.strip()
					x 				= row.getValue(FoundationType)
					foundationType  = x.strip()
					numStories 		= row.getValue(NumStories)
					area 			= row.getValue(Area)    # Used in Inventory Loss Calculation

					# Construct the strings for the LUT reference: if depth <0, use 'm'. If >0, use 'p'
					# See the Column headings in the csv lookup tables.
					# Need to strip out the minus sign using abs() and the decimal point using int(), and convert it to a string using str()
					suffix_l = str(int(abs(math.floor(depth))))
					suffix_u = str(int(abs(math.ceil(depth))))
					prefix_l = 'm' if math.floor(depth) < 0 else 'p'
					prefix_u = 'm' if math.ceil(depth) < 0 else 'p'  # Need to fuss over the boundary case  -1 < depth < 0
					l_index = prefix_l + suffix_l
					u_index = prefix_u + suffix_u

					###########################################################
					# BUILDING LOSS CALCULATION
					###########################################################
					# Did user specify a Building DDF? If so, use that to reference the Full LUT, else use the Default LUT.
					# Due to Hazus-MH Flood definitions, this is Text type.
					BID = row.getValue(BldgDamageFnID) if ubddf else None

					# If BID is specified by the user, and defined, then assume they know what is best, and use the full lookup table.
					# Tests are ok if you go left-to-right. Go from most-basic-test-to-more-advanced in the same line.  Can't flip the order here!
					if BID is not None and BID != '' and BID in bddf_lut_full_list:
						# Search the  full lookup table to find the DDF_ID that matches the BID
						# 'gotcha' checks for no hits - set a check bit - that should not happen, given the membership test with bddf_lut_full_list.
						# For more efficiency, break out of the loop if it is found
						gotcha = 0
						for lutrow in bddf_lut_full:
							if lutrow['BldgDmgFnID'] == BID:	# This is a string match. For completeness and trailing spaces, may want to make it an integer?
								gotcha += 1
								ddf1 = lutrow
								# Notify user if the OccupancyClass associated with the user-specified DDFID is inconsistent with the user-supplied OccupancyClass
								# This is not harmful; DOGAMI script has chosen to just process it (Hazus silently reverts back to the default!)
								# Simple notification
								OccClsCheck = ddf1['Occupancy']
								if OccClsCheck != OC and QC_Warning:
									arcpy.AddWarning("FYI: User-supplied Building DDFID " + BID + " Occupancy Class is inconsistent with UDF Occupancy Class " + OC + " versus "+OccClsCheck+ "  " + userDefinedFltyId)
								break
						d_lower = float(ddf1[l_index])
						d_upper = float(ddf1[u_index])
						ddf_id = int(BID)  # Yes, it is redundant to post, again, what the user specified. But it is consistent with Default LUT

					else:
						# We may have gotten here because of a bad BDDF code. If so, revert to the default and notify user
						# Note we are in the Default DDF section, and will calculate loss in that manner.
						if QC_Warning and BID is not None and BID != '' and int(BID)>0:
							arcpy.AddWarning("User specified a non-official Building DDFID: " + BID + "    UID: " + userDefinedFltyId )
							arcpy.AddWarning("   Reverting to default Building DDF for Occupancy Class " + OC)

						# Go through the lookup table, one row at a time to find the Structure of interest
						# 'gotcha' checks for no hits - set a check bit
						# Also, for more efficiency, break out of the loop if it is found
						gotcha = 0

						# Change DDF table only if Coastal Zone is defined (CoastalZoneSuppled) AND a legitimate Coastal Zone Code (AE, V, VE)
						# Otherwise use default ddf.
						# As of Hazus 4.0, Coastal lookup tables are only applicable for RES-type structures.
						blut = bddf_lut_riverine
						if CoastalZoneSupplied and OC[:3] =='RES':
							if CoastalZoneCode == 'CAE' :
								blut = bddf_lut_coastalA
							if CoastalZoneCode == 'VE' or CoastalZoneCode == 'V':
								blut = bddf_lut_coastalV

						# Now do the lookup in the Default DDF
						for lutrow in blut:
							if lutrow['SpecificOccupId'] == SpecificOccupId:
								gotcha += 1
								ddf1 = lutrow
								ddf_id = lutrow['DDF_ID']   # For the Record. Will go in the Results file.
								break # Quit once you found it.
						if gotcha == 0:
							# This should not occur
							arcpy.AddError( "something wrong, no match for Specific Occupancy ID :" + SpecificOccupId + "   UDF: " + UserDefinedFltyId)
							arcpy.AddMessage(arcpy.GetMessages(0))
							sys.exit(2)

					# Dictionary lookup: get damage percentage for the particular row at the particular depths
					# The Dictionary element comes from either the Full or the Default table; common code after this point.
					d_lower = float(ddf1[l_index])
					d_upper = float(ddf1[u_index])
					# Get fractional amount of depth, for interpolation
					frac = depth - math.floor(depth)
					damage = (d_lower + frac*(d_upper - d_lower))/100

					if gotcha == 0:
						# This should not occur, given the memebership test with bddf_lut_full_list. Just in case:
						arcpy.AddError("Problem: nothing matches the SpecificOccupId of " + SpecificOccupId + "     Check entry UDFID " + userDefinedFltyId + " with " + OC )
						SpecificOccupId = "XXXX"
						BDDF_ID = LR = bldg_loss = -9999

					# Calculate building loss, set other attributes
					row.setValue(SOID,SpecificOccupId)
					row.setValue(BDDF_ID,ddf_id)
					row.setValue(BldgDmgPct,damage*100)  # Hazus convention: percentage
					bldg_loss = damage * row.getValue(Cost)
					row.setValue(BldgLossUSD,bldg_loss)

					###########################################################
					# CONTENT LOSS CALCULATION
					###########################################################
					# Did user specify a Content DDF? If so, use that to reference the Full LUT, else use the Default LUT.
					# Due to Hazus-MH Flood conventions, the CDDF_ID is of type Text
					BID = row.getValue(ContDamageFnId)if ucddf else None

					# If BID is specified by the user, then assume they know what is best, and use the full lookup table.
					# Tests are ok if you go left-to-right. Go from most-basic-test-to-more-advanced in the same line.  Can't flip the order here!
					if BID is not None and BID != '' and BID in cddf_lut_full_list:
						# Search the  full lookup table to find the DDF_ID that matches the BID
						# 'gotcha' checks for no hits - set a check bit - that should not happen, given the membership test with bddf_lut_full_list.
						# For more efficiency, break out of the loop if it is found
						gotcha = 0
						for lutrow in cddf_lut_full:
							if lutrow['ContDmgFnId'] == BID:	# This is a string match. For completeness and trailing spaces, may want to make it an integer?
								gotcha += 1
								ddf1 = lutrow
								# Notify user if the OccupancyClass associated with the user-specified DDFID is inconsistent with the user-supplied OccupancyClass
								# This is not harmful; DOGAMI script has chosen to just process it (Hazus silently reverts back to the default!)
								# Simple notification
								OccClsCheck = ddf1['Occupancy']
								if OccClsCheck != OC and QC_Warning:
									arcpy.AddWarning("FYI: User-supplied Content  DDFID " + BID + " Occupancy Class is inconsistent with UDF Occupancy Class " + OC + " versus "+OccClsCheck+ "  " + userDefinedFltyId)
								break
						d_lower = float(ddf1[l_index])
						d_upper = float(ddf1[u_index])
						ddf_id = int(BID)  # Yes, it is redundant to post, again, what the user specified. But it is consistent with Default LUT

					else:
						# We may have gotten here because of a bad CDDF code. If so, revert to the default and notify user
						# Note we are in the Default DDF section, and will calculate loss in that manner.
						if QC_Warning and BID is not None and BID != '' and int(BID)>0:
							arcpy.AddWarning( "FYI: User specified a non-official Content DDFID: " + BID + "    UID: " + userDefinedFltyId + "   Reverting to default Content DDF for Occupancy Class " + OC)

						# Go through the lookup table, one row at a time to find the Structure of interest
						# 'gotcha' checks for no hits - set a check bit
						# Also, for more efficiency, break out of the loop if it is found
						gotcha = 0

						# Change DDF table if Coastal; otherwise use default ddf.
						# As of Hazus 4.0, Coastal lookuptables only applicable for RES-type structures.
						# Need to filter out "REL" from "RES" - look at second letter
						clut = cddf_lut_riverine
						if CoastalZoneSupplied and OC[:3] =='RES':
							if CoastalZoneCode == 'CAE' :
								clut = cddf_lut_coastalA
							if CoastalZoneCode == 'VE' or CoastalZoneCode == 'V':
								 clut = cddf_lut_coastalV

						for lutrow in clut:
							if lutrow['SpecificOccupId'] == SpecificOccupId:
								gotcha += 1
								ddf1 = lutrow
								ddf_id = lutrow['DDF_ID']   # For the Record. Will go in the Results file.
								break # Quit once you found it.
						if gotcha == 0:
							# This should not occur
							arcpy.AddError("something wrong for Content lookup, no match for Specific Occupancy ID :" + SpecificOccupId + "   Counter:" + str(counter))


					# Dictionary lookup: get damage percentage for the particular row at the particular depths
					# The Dictionary element comes from either the Full or the Default table; common code after this point.
					d_lower = float(ddf1[l_index])
					d_upper = float(ddf1[u_index])
					# Get fractional amount of depth, for interpolation
					frac = depth - math.floor(depth)
					damage = (d_lower + frac*(d_upper - d_lower))/100

					if gotcha == 0:
						# Should not occur, given the check for membership in the list. But here just in case
						arcpy.AddWarning("Problem with Content Loss: nothing matches the SpecificOccupId of " + SpecificOccupId + "Check entry " + str(counter) + " with " + OC + " " + str(numStories))
						SpecificOccupId = "XXXX"
						CDDF_ID = LR = bldg_loss = -9999

					row.setValue(CDDF_ID,ddf_id)
					row.setValue(ContDmgPct,damage*100)   # Hazus convention: percenage
					content_loss = damage*ccost
					row.setValue(ContentLossUSD,content_loss)

					###########################################################
					# INVENTORY LOSS CALCULATION
					###########################################################
					# Did user specify an Inventory DDF? If so, use that to reference the Full LUT, else use the Default LUT.
					# Due to Hazus-MH Flood conventions, the IDDF_ID is of type Text
					BID = row.getValue(InvDamageFnId) if uiddf else None
					# If BID is specified by the user, then assume they know what is best, and use the full lookup table.
					# Tests are ok if you go left-to-right. Go from most-basic-test-to-more-advanced in the same line.  Can't flip the order here!
					if BID is not None and BID != '' and BID in iddf_lut_full_list:
						# Search the  full lookup table to find the DDF_ID that matches the BID
						# 'gotcha' checks for no hits - set a check bit - that should not happen, given the membership test with bddf_lut_full_list.
						# For more efficiency, break out of the loop if it is found
						gotcha = 0
						for lutrow in iddf_lut_full:
							if lutrow['InvDmgFnId'] == BID:	# This is a string match. For completeness and trailing spaces, may want to make it an integer?
								gotcha += 1
								ddf1 = lutrow
								# Notify user if the OccupancyClass associated with the user-specified DDFID is inconsistent with the user-supplied OccupancyClass
								# This is not harmful; DOGAMI script has chosen to just process it (Hazus silently reverts back to the default!)
								# Simple notification
								OccClsCheck = ddf1['Occupancy']
								if OccClsCheck != OC and QC_Warning:
									arcpy.AddWarning("FYI: User-supplied Inventory DDFID " + BID + " Occupancy Class is inconsistent with UDF Occupancy Class " + OC + " versus "+OccClsCheck+ "  " + userDefinedFltyId)
								break
						d_lower = float(ddf1[l_index])
						d_upper = float(ddf1[u_index])
						frac = depth - math.floor(depth)
						damage = (d_lower + frac*(d_upper - d_lower))/100
						ddf_id = int(BID)  # Yes, it is redundant to post, again, what the user specified. But it is consistent with Default LUT

					else:
						# We may have gotten here because of a bad IDDF code. If so, revert to the default and notify user
						# Note we are in the Default DDF section, and will calculate loss in that manner.
						if QC_Warning and BID is not None and BID != '' and int(BID)>0:
							arcpy.AddWarning( "User specified a non-official Inventory DDFID: " + BID + "    UID: " + userDefinedFltyId + "   Reverting to default Inventory DDF for Occupancy Class " + OC)

						# Go through the lookup table, one row at a time to find the Structure of interest
						# 'gotcha' checks for no hits - set a check bit
						# Also, for more efficiency, break out of the loop if it is found
						gotcha = 0

						# Inventory: There is no Coastal Flooding default table to use
						ilut = iddf_lut_riverine

						# Default Inventory DDF defined only for a subset of OccupancyClass types
						if OC in Inventory_List:
							for lutrow in ilut:
								if lutrow['SpecificOccupId'] == SpecificOccupId:
									gotcha += 1
									ddf1 = lutrow
									ddf_id = lutrow['DDF_ID']   # For the Record. Will go in the Results file.
									break # Quit once you found it.
							if gotcha == 0:
								# This should not occur
								arcpy.AddError("something wrong for Inventory lookup, no match for Specific Occupancy ID :" + SpecificOccupId + "   Counter:" + str(counter))
								arcpy.AddMessage(arcpy.GetMessages(0))
								sys.exit(2)

							# Dictionary lookup: get damage percentage for the particular row at the particular depths
							# The Dictionary element comes from either the Full or the Default table; common code after this point.
							d_lower = float(ddf1[l_index])
							d_upper = float(ddf1[u_index])
							# Get fractional amount of depth, for interpolation
							frac = depth - math.floor(depth)
							damage = (d_lower + frac*(d_upper - d_lower))/100

							if gotcha == 0:
								# Should not occur, given the check for membership in the list. But here just in case
								arcpy.AddWarning("Problem with Inventory Loss: nothing matches the SpecificOccupId of " + SpecificOccupId + "Check entry " + str(counter) + " with " + OC + " " + str(numStories))
								SpecificOccupId = "XXXX"
								IDDF_ID = LR = bldg_loss = -9999


						else:
							# No default DDF ID exists for the given OccupancyClass. Fill them in with zeros
							damage = 0
							ddf_id = 0

					row.setValue(IDDF_ID,ddf_id)
					row.setValue(InvDmgPct,damage*100)  # Hazus convention - percentage

					# Inventory Loss in US$: depends if user supplied an inventory cost field, and if it is > 0.
					# If not supplied, or 0, then use the default value based on OccupancyClass and Square Footage
					# per Hazus-MH Flood Technical Manual table
					# But note that the 'default value' is defined only for a subset of OccupancyClasses
					# Logic spelled out in accompanying spreadsheet - to simplify it, create three variables
					# OWDI = OccupancyClass with Default Inventory
					# USID = User-supplied Inventory DDF is supplied and legitimate
					# USIC = User-supplied Inventory Cost is supplied and non-zero and non-null


					inventory_loss = damage * icost
					row.setValue(InventoryLossUSD,inventory_loss)

					###########################################################
					# DEBRIS CALCULATIONS
					###########################################################
					# Calculate only for exposed buildings
					if depth is not None:
						# Build up a DebrisID key for accessing Debris LUT table
						# Basement/No Basement only defined for RES1.
						# Slab/Footing: Simple mapping of FoundationType (includes Basement by definition)
						# dsuf = depth suffix
						bsm = 'NB'   # No Basement is the default. Only override for RES1
						fnd = 'SG' if (foundationType == '4' or foundationType == '7') else 'FT'  # SG: Slab on Grade.  FT = ???? DEFINE THIS - FROM BBOHN.
						# Flood depth key varies, depending if it's a RES1/Basement.
						if OC == 'RES1' and foundationType == '4':
							bsm = 'B'
							dsuf = '-8' if depth <-4 else '-4' if depth < 0 \
								else '0' if depth <4 else '4' if depth < 6 \
								else '6' if depth <8 else '8'
						else:  # Credit to BBohn who identified 0/1/4/8/12 as common breakpoints shared by all non-RES1-Basement
							dsuf = '0' if depth <1 else '1' if depth < 4 \
						  	else '4' if depth <8 else '8' if depth < 12 else '12'
						debriskey = OC + bsm + fnd + dsuf

						for lutrow in debris_lut:
							if lutrow['DebrisID'] == debriskey:	# This is a string match. For completeness and trailing spaces, may want to make it an integer?
								gotcha += 1
								ddf1 = lutrow
						dfin_rate	=  float(ddf1['Finishes'])
						dstruc_rate =  float(ddf1['Structure'])
						dfound_rate =  float(ddf1['Foundation'])
						# All LUT numbers are in tons per 1000 square feet, so adjust for your particular structure
						dfin		= area * dfin_rate / 1000
						dstruc		= area * dstruc_rate / 1000
						dfound		= area * dfound_rate / 1000
						dtot		= dfin + dstruc + dfound
					else:
						dfin = dstruc = dfound = dtot = debriskey = None

					row.setValue(DebrisID,debriskey)
					row.setValue(Debris_Fin,dfin)
					row.setValue(Debris_Struc,dstruc)
					row.setValue(Debris_Found,dfound)
					row.setValue(Debris_Tot,dtot)

					###########################################################
					# Restoration Time Calculation - the basis for all Direct Economic Loss numbers
					# Based on the Min and Max days listed in   [dbo].[flRsFnGBS]
					# Note how the table differs slightly from the TM, esp with Res with basements
					# Note that the TM suggests some of these are not subject to a 10% threshold
					# The method suggests using the Maximum; for completeness, the script produces both.
					###########################################################
					# Calculate only for exposed buildings.
					if depth is not None:
						# Build up a key for accessing the Restoration Time LUT table
						dsuf = '0' if depth <0 else '1' if depth < 1 \
						  	else '4' if depth <4 else '8' if depth < 8 else '12' if depth < 12 else '24'
						RsFnkey = OC + dsuf
						for lutrow in rest_lut:
							if lutrow['RestFnID'] == RsFnkey:	# This is a string match. For completeness and trailing spaces, may want to make it an integer?
								ddf1 = lutrow
								break
						restdays_min =  int(ddf1['Min_Restor_Days']) # This is the maximum days out (flRsFnGBS has a min and a max)
						restdays_max =  int(ddf1['Max_Restor_Days']) # This is the maximum days out (flRsFnGBS has a min and a max)
					else:
						restdays_min = restdays_max = 0   # Or should it be None type?
					row.setValue(Restor_Days_Min,restdays_min)
					row.setValue(Restor_Days_Max,restdays_max)

				# When running multiple grids, sensitivity tests, etc, adding the gridname makes it easier to sort upon an appended dataset
				row.setValue(GridName,gridroot)
				cursor.updateRow(row)

			arcpy.AddMessage("Total records processed: " + str(counter))

		del row
		del cursor
		arcpy.CheckInExtension("Spatial")  # Be a mensch

		# Measuring the script performance
		arcpy.AddMessage(" ")
		arcpy.AddMessage("Program Duration:  %s seconds" %  int((time.time() - start_time)))
	except:
		tb = sys.exc_info()[2]
		tbinfo = traceback.format_tb(tb)[0]
		pymsg = ("PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n" + str(sys.exc_type) + ": " + str(sys.exc_value) + "\n")
		msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"
		arcpy.CheckInExtension("Spatial")  # Be a mensch
		arcpy.AddError(msgs)
		arcpy.AddError(pymsg)
		arcpy.AddMessage(arcpy.GetMessages(1))

# This test allows the script to be used from the operating
# system command prompt (stand-alone), in a Python IDE,
# as a geoprocessing script tool, or as a module imported in
# another script
if __name__ == '__main__':
	# Arguments are defined in flood_damage defined above
	argv = tuple(arcpy.GetParameterAsText(i)
		for i in range(arcpy.GetArgumentCount()))
	flood_damage(*argv)



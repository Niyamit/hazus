from tkinter import *
from tkinter import filedialog
import hazus,os, csv
from os import listdir
from os.path import isfile, join

dir = os.getcwd()
#dir = os.path.dirname(dir)
cwd = os.path.join(dir,'rasters')# Default raster directory
rasters = [f for f in listdir(cwd) if isfile(join(cwd, f)) and f.endswith('.tif')]# Search rasters folder for all .tif files and make a list
print('Rasters selection ',rasters)
#hazardTypes = {'Riverine':'HazardR','CoastalA':'HazardCA','CoastalB':'HazardCV'}
#fields = ['Occupancy*','NumStories*','SpecificOcc_ID','BuildingDDF','ContentDDF','InventoryDDF','Hazard-Type*']# Fields for custom input
fields = {'UserDefinedFltyId':'UserDefinedFltyId*',
          'OCC':'Occupancy Class*',
          'Cost':'Cost*',
          'ContentCost':'Content Cost*',
          'Area':'Area*',
          'NumStories':'Number of Stories*',
          'FoundationType':'Foundation Type*',
          'FirstFloorHt':'First Floor Height*',
          'BDDF_ID':'BldgDamageFnID',
          'CDDF_ID':'ContDamageFnId',
          'IDDF_ID':'InvDamageFnId',
          'InvCost':'Inventory Cost',
          'SOID':'Specific Occupancy ID',
          'flC':'f1C',
          'Latitude':'Latitude*',
          'Longitude':'Longitude*',
          'raster':'Depth Grid (ft)*'}

#fields = {'OCC':'Occupancy*','NumStories':'NumStories*','SOID':'SpecificOcc_ID','BDDF_ID':'BuildingDDF','CDDF_ID':'ContentDDF','IDDF_ID':'InventoryDDF','raster':'Depth Grid (ft)*'}# Fields for custom inpu
defaultFields = {'OCC':['Occupancy','Occ'],
                 'NumStories':['NumStories','NumberStories','Num_Stories','Number_Stories'],
                 'SOID':['SpecificOcc_ID','SOID'],
                 'BDDF_ID':['BuildingDDF','BDDF_ID'],
                 'CDDF_ID':['ContentDDF','CDDF_ID'],
                 'IDDF_ID':['InventoryDDF','IDDF_ID'],
                 'InvCost':['InvCost','invcost'],
                 'UserDefinedFltyId':['UserDefinedFltyId','userdefinedfltyid'],
                 'Cost':['Cost','COST','cost'],
                 'ContentCost':['ContentCost','CONTENTCOST','contentcost','Content_Cost','content_cost','Content_cost'],
                 'Area':['Area','area','AREA'],
                 'FoundationType':['FoundationType'],
                 'FirstFloorHt':['FirstFloorHt'],
                 'flC':['f1C','f1c','F1C','F1c'],
                 'Latitude':['Latitude','latitude','LATITUDE',],
                 'Longitude':['Longitude','longitude','LONGITUDE']}
#fields = ['Occupancy','NumStories','SOID','BDDF_ID','CDDF_ID','IDDF_ID','Hazard-Type']# Fields for custom input

def runHazus():
    entries = []
    print(fields)
    entries.extend(root.fields.values())
    #entries.append(ents['Hazard-Type*'].get(ents['Hazard-Type*'].curselection()))
    """
    for num, ent in enumerate(ents):# Construct a list for field names and their values for field mapping 
        if fields[num] == 'Hazard-Type*':
            entries.append([fields[num],ents[fields[num]].get(ents[fields[num]].curselection())])
        #else:
            #entries.append([fields[num],ents[fields[num]].get()])
    """
    print(entries)
    haz = hazus.local(root.filename, entries)# Run the Hazus script with input from user using the GUI

    print('Run Hazus',haz,entries)

def browse_button():
    root.filename = filedialog.askopenfilename(initialdir = "/",title = "Select file",filetypes = (("csv files","*.csv"),("all files","*.*")))# Gets input csv file from user
    # Gets field names from input csv file and makes a list
    with open(root.filename, "r+") as f:
        reader = csv.reader(f)
        root.csvFields = next(reader)
    print(root.filename,root.csvFields)

def makeform(root, fields):# Assemble and format the fields to map from the list of fields
   entries = {}
   
   for field in fields.values():# Make entry box for each field
      row = Frame(root)
      lab = Label(row, width=22, text=field+": ", anchor='w')
          
      if field == 'Depth Grid (ft)*':
          ent = Listbox(row,exportselection=0)
          for num, raster in enumerate(rasters): ent.insert(num, raster)
          ent.selection_set(0)
          
      else:
          ent = Entry(row)
          
      row.pack(side=TOP, fill=X, padx=5, pady=5)
      lab.pack(side=LEFT)
      ent.pack(side=RIGHT, expand=YES, fill=X)
      entries[field] = ent  
   return entries

def checkform():# Check validity of form entries
   for key, field in fields.items():
       if field != 'Depth Grid (ft)*':# Not needed for raster input box
           color = "yellow"
           ent = ents[field]
           value = ent.get()
           if '*' in field: root.valid[field] = False
           if len(root.csvFields) == 0:
               color = "red"# If no input file is selected or it's invalid, the field is red
           elif value != '':
               if value in root.csvFields:
                   root.fields[key] = value
                   color = "green"
                   if '*' in field: root.valid[field] = True
           else:
               for defaultField in defaultFields[key]:
                   if defaultField in root.csvFields:
                       root.fields[key] = root.csvFields[root.csvFields.index(defaultField)]
                       color = "green"
                       if '*' in field: root.valid[field] = True
                       break
           ent.config(background=color)   
       else: root.fields[key] = ents[field].get(ents[field].curselection())
            
   
   if False in root.valid.values(): b1.config(fg='grey',command='')
   else: b1.config(fg='black', command=runHazus)
   root.after(100, checkform)#Recheck fields every 0.1 second
              
if __name__ == '__main__':
   root = Tk()
   root.csvFields = []# Input csv file fields
   root.fields = {key:''for key, value in fields.items()}
   root.valid = {}
   ents = makeform(root, fields)
   b1 = Button(root, text='Execute', command=runHazus, fg = 'Grey')# Run button to start processing
   b1.pack(side=LEFT, padx=5, pady=5)
   b2 = Button(root, text="Browse to Inventory Input (.csv)", command=browse_button)# Browse for input csv file
   b2.pack(side=LEFT, padx=5, pady=5)
   b3 = Button(root, text='Quit', command=root.quit)
   b3.pack(side=LEFT, padx=5, pady=5)
   root.after(100, checkform)# Recheck fields every 0.1 second
   root.mainloop()
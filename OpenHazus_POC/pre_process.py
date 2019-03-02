import os, csv

dir = os.getcwd()

def process(input,fmap):
    output = input.split('.')[0]+'_pre_processed.csv'
    print(output)
    OCC,NumStories,SOID,BDDF_ID,CDDF_ID,IDDF_ID,HazardType = fmap#[value if value != '' and any(value in s for s in defaultFields) == True else field for field, value in fmap]
    SOID = SOID if SOID != '' else 'SOID'
    BDDF_ID = BDDF_ID if BDDF_ID != '' else 'BDDF_ID'
    BDDF_ID = BDDF_ID if BDDF_ID != '' else 'BDDF_ID'
    CDDF_ID = CDDF_ID if CDDF_ID != '' else 'CDDF_ID'
    IDDF_ID = IDDF_ID if IDDF_ID != '' else 'IDDF_ID'
    
    LUT_Dir = os.path.join(dir,'lookuptables')
    
    #OCC,NumStories,SOID,BDDF_ID,CDDF_ID,IDDF_ID,HazardType = ['Occ','NumStories','SOID','BDDF_ID','CDDF_ID','IDDF_ID','HazardR']
    #Custom DDF assignment based on tables	
    DDFAssign = ['SOoccupId_Occ_Xref','flBldgStructDmgFinal','flBldgContDmgFinal','flBldgInvDmgFinal','OccupancyTypes']
    DDFTables = {}
    for DDF in DDFAssign:
        with open(os.path.join(LUT_Dir,DDF+'.csv'), newline='') as csvfile:
            file = csv.DictReader(csvfile)
            DDFTable = [row for row in file]
            DDFTables[DDF] = DDFTable
            
    countie = [0,0,0,0]
    counter = 0

    with open(input, "r+") as f:
        reader = csv.reader(f)
        field_names = next(reader)

    with open(input, newline='') as csvfile:
        field_names.extend(['SOID','BDDF_ID','CDDF_ID','IDDF_ID'])
        print(field_names)
        writer = csv.DictWriter(open(output, 'w'), delimiter=',', lineterminator='\n', fieldnames = field_names)
        file = csv.DictReader(csvfile)
        for row in file:
            value = 0
            if row.get(SOID) == None and SOID != '':
                for line in DDFTables['SOoccupId_Occ_Xref']:
                    if line['Occupancy'].strip() == row[OCC] and line['NumStoriesInt'] == row[NumStories]:
                        value = line['SOccupId'].strip()
                        row[SOID] = value
                        countie[0] = countie[0] + 1
                        break
            if row.get(BDDF_ID) == None and BDDF_ID != '':
                for line in DDFTables['flBldgStructDmgFinal']:
                    if line['SOccupId'].strip() == value and int(line[HazardType]) == 1:
                        row[BDDF_ID] = line['BldgDmgFnId']
                        countie[1] = countie[1] + 1
                        break
            if row.get(CDDF_ID) == None and CDDF_ID != '':    
                for line in DDFTables['flBldgContDmgFinal']:
                    if line['SOccupId'].strip() == value and int(line[HazardType]) == 1:
                        row[CDDF_ID] = line['ContDmgFnId']
                        countie[2] = countie[2] + 1
                        break
            if row.get(IDDF_ID) == None and IDDF_ID != '':   
                for line in DDFTables['flBldgInvDmgFinal']:
                    if line['SOccupId'].strip() == value and int(line[HazardType]) == 1:
                        row[IDDF_ID] = line['InvDmgFnId']
                        countie[3] = countie[3] + 1
                        break
            
            counter += 1
            if counter % 10000 == 0:
                print( "   processing record " + str(counter),  ' countie = ', countie)
                
            if counter == 1:
                writer.writeheader()
                writer.writerow(row)
                continue
            writer.writerow(row)
        print("Total records processed: " + str(counter),  ' countie = ', countie)


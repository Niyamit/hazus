from tkinter import *
from tkinter import filedialog
import hazus, os, csv
from os import listdir
from os.path import isfile, join

input = 'Depth Grid (ft)'# Default name for the raster selection box
fields = ['UserDefinedFltyId','OccupancyClass','Cost','ContentCost','Area','NumStories','FoundationType','FirstFloorHt','BldgDamageFnID','ContDamageFnId','InvDamageFnId','InvCost','flC','Latitude','Longitude',input]# Fields for custom input
dir = os.getcwd()# Get current directory of script to find rasters folder
cwd = os.path.join(dir,'rasters')# Default raster directory
rasters = [f for f in listdir(cwd) if isfile(join(cwd, f)) and f.endswith('.tif')]# Search rasters folder for all .tif files and make a list
print('Rasters selection ',rasters)

def runHazus():
    entries = []
    for num, ent in enumerate(ents):# Construct a list for field names and their values for field mapping
        if fields[num] == input:
            entries.append([fields[num],ents[fields[num]].get(ents[fields[num]].curselection())])   
        else:
            entries.append([fields[num],ents[fields[num]].get()])
    print(entries)
    haz = hazus.local(root.filename, entries)# Run the Hazus script with input from user using the GUI
    print('HAZUS RUN',haz,entries)

def browse_button():
    root.filename = filedialog.askopenfilename(initialdir = "/",title = "Select file",filetypes = (("csv files","*.csv"),("all files","*.*")))# Gets input csv file from user
    # Gets field names from input csv file and makes a list
    with open(root.filename, "r+") as f:
        reader = csv.reader(f)
        root.csvFields = next(reader)
    print(root.filename,root.csvFields)

def makeform(root, fields):# Assemble and format the fields to map from the list of fields
   entries = {}
   
   for field in fields:# Make entry box for each field
      row = Frame(root)
      lab = Label(row, width=22, text=field+": ", anchor='w')
      if field == input:# Aside from raster input field which is a listbox not text entry
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
   for field in fields:
       if field != input and field != 'Hazard-Type':# Not needed for raster input box
            ent = ents[field]
            value = ent.get()
            if value in root.csvFields or field in root.csvFields:# Check if current field map input matches a field from the input csv file OR the default field name
                ent.config(background="green")# If it does, the field is green
            elif len(root.csvFields) != 0:
                ent.config(background="yellow")# If it doesn't the field is yellow
            else:
                ent.config(background="red")# If no input file is selected or it's invalid, the field is red
   root.after(100, checkform)#Recheck fields every 0.1 second
              
if __name__ == '__main__':
   root = Tk()
   root.csvFields = []# Input csv file fields
   ents = makeform(root, fields)
   b1 = Button(root, text='Execute', command=runHazus)# Run button to start processing
   b1.pack(side=LEFT, padx=5, pady=5)
   b2 = Button(root, text="Browse to Inventory Input (.csv)", command=browse_button)# Browse for input csv file
   b2.pack(side=LEFT, padx=5, pady=5)
   b3 = Button(root, text='Quit', command=root.quit)
   b3.pack(side=LEFT, padx=5, pady=5)
   root.after(100, checkform)# Recheck fields every 0.1 second
   root.mainloop()
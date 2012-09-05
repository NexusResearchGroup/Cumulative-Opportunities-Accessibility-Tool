# ----------
# COA_Tool.py
# by Andrew Owen
# Calculates the cumulative opportunities accessibility for each feature in the
# source feature classes based on feature-feature travel times provided in the
# travel time tables. The results are output in a separate table.

import arcpy

from arcpy import SearchCursor
from arcpy import InsertCursor
from arcpy import AddMessage as AM
from arcpy import AddError as AE
from arcpy import GetParameterAsText
from arcpy import env
from arcpy import SetProgressor
from arcpy import SetProgressorLabel
from arcpy import ResetProgressor
from arcpy import SetProgressorPosition

from arcpy.management import CreateTable
from arcpy.management import AddField
from arcpy.management import GetCount

from os.path import split,join

# Functions and classes

def parseInputTablename(tablename):
	'''
	Parses an accessibility input table name into components type, subject, subject_year, scale, and scale_year.
	
	For example:
	>>> parseInputFilename("lu_jobs2010_taz2000")
	('lu', 'jobs', '2010', 'taz', '2000')
	'''
	type, subject, scale = tablename.split("_")
	subject_year = subject[-4:]
	subject = subject[:-4]
	scale_year = scale[-4:]
	scale = scale[:-4]
	
	return type, subject, subject_year, scale, scale_year

def createOutputFilename(mode, mode_year, destination, destination_year, scale, scale_year):
	return "acc" + "_" + destination + destination_year + "_" + mode + mode_year + "_" + scale + scale_year
	
class TravelTimeTable:

	def __init__(self, table_name=None):
		if table_name != None:
			self.loadTTFromTable(table_name)

	def keyForPair(self, oid, did):
		return oid + "-" + did
			
	def loadTTFromTable(self, table_name):
		AM("Loading travel times from table: " + table_name)
		self.table = {}
		
		type, subject, subject_year, scale, scale_year = parseInputTablename(table_name)
		
		oid_field_name = "o" + scale
		did_field_name = "d" + scale
		time_field_name = "mins"
		
		pairs = SearchCursor(table_name)
		for pair in pairs:
			pair_id = self.keyForPair(str(pair.getValue(oid_field_name)), str(pair.getValue(did_field_name)))
			
			if pair_id in self.table:
				AE("Duplicate OP pair: " + str(pair_id))
			
			else:
				self.table[pair_id] = pair.getValue(time_field_name)	
	
	def timeFromTo(self, oid, did):
		return self.table[self.keyForPair(oid, did)]

class LandUseTable:
	
	def __init__(self, table_name=None):
		if table_name != None:
			self.loadLUFromTable(table_name)
	
	def loadLUFromTable(self, table_name):
		self.table = {}
		
		type, subject, subject_year, scale, scale_year = parseInputTablename(table_name)
		
		id_field_name = scale
		count_field_name = "n" + subject
		
		features = SearchCursor(table_name)
		for feature in features:
			feature_id = str(feature.getValue(id_field_name))
			
			if feature_id in self.table:
				AE("Duplicate feature ID: " + feature_id)
				
			else:
				opportunities = feature.getValue(count_field_name)
				if opportunities == None:
					opportunities = 0
				self.table[feature_id] = opportunities
	
	def listIDs(self):
		return sorted(self.table.keys())

	def opportunitiesAtFeature(self, id):
		return self.table[id]
	
# Get parameters
#AM("Get parameters")
tt_inputs               = GetParameterAsText(0).split(";")
lu_inputs              	= GetParameterAsText(1).split(";")
output_workspace        = GetParameterAsText(2)

# Set environment, preserving original values
original_workspace = env.workspace

thresholds = range(5,65,5)

SetProgressor("step", "Calculating cumulative opportunities accessibilty...", 0, len(tt_inputs) * len(lu_inputs) * len(thresholds), 1)

for tt_input in tt_inputs:
	AM("Processing TT table: " + tt_input)
	tt_table = TravelTimeTable(tt_input)
	type, mode, mode_year, t_scale, t_scale_year = parseInputTablename(tt_input)
	
	for lu_input in lu_inputs:
		AM("Processing LU table: " + lu_input)
		lu_table = LandUseTable(lu_input)
		type, destination, destination_year, d_scale, d_scale_year = parseInputTablename(lu_input)
		
		if t_scale != d_scale or d_scale_year != t_scale_year:
			AM("Geographic scales of land use and travel time do not match.")
		
		# Create a table to hold the results
		out_table = createOutputFilename(mode, mode_year, destination, destination_year, t_scale, t_scale_year)
		env.workspace = output_workspace
		CreateTable(output_workspace, out_table)
		AddField(out_table, t_scale, "TEXT", field_length=15)
		for threshold in thresholds:
			field_name = "t"+str(threshold)
			AddField(out_table, field_name, "LONG")
		
		# Populate the output table
		cursor = InsertCursor(out_table)
		for oid in lu_table.listIDs():
			row = cursor.newRow()
			row.setValue(t_scale, oid)

			for threshold in thresholds:
				field_name = "t"+str(threshold)
				opportunities = 0
				for did in lu_table.listIDs():
					if tt_table.timeFromTo(oid, did) <= threshold:
						opportunities = opportunities + lu_table.opportunitiesAtFeature(did)
				row.setValue(field_name, opportunities)
				
			cursor.insertRow(row)
	
# Restore original environment
env.workspace = original_workspace



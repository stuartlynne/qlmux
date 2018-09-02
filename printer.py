
import sys
import itertools
import datetime
from Queue import Queue, Empty
from enum import Enum
#from easysnmp import snmp_get, snmp_set, snmp_walk
from easysnmp import Session
import re
import select
import socket
from threading import Thread as Process
from time import sleep

getTimeNow = datetime.datetime.now


from snmp import SNMPStatus

class PrinterStatus (Enum):
	UNKNOWN = 0
	NOTAVAILABLE = 1
	OK = 2
	PRINTING = 3



class Job( object ):
	def __init__(self, pool, data):
		self.pool = pool
		self.data = data

	def __repr__(self):
		return "\nJob[%s] %s " % ( self.pool, len(self.data))


#
# Printer
# Destinations for data.
#
#
class Printer( object ):

	def __init__(self, name, testport):
		self.name = name
		self.testport = testport
		self.status = PrinterStatus.UNKNOWN
		self.snmpstatus = SNMPStatus.UNKNOWN
		self.snmpvalue = ''
		self.fd = None
		self.pool = None
		self.printjobs = []
		self.currentjob = None
		self.senddata = None
		self.sending = False
		self.count = 0

		self.snmpsession = Session(hostname=name, community='public', version=1, timeout=.2, retries=0)


	# update the printer status using SNMP
	#
	def updatestatus(self):

		oldstatus = self.snmpstatus
		#print('Printer:updatestatus[%s]: %s' % (self.name, self.snmpsession))
		try:
			data = self.snmpsession.get('iso.3.6.1.4.1.11.2.4.3.1.2.0')
			self.snmpvalue = data.value
			#print('Printer:updatestatus[%s] data' % (data))
		except:
			#print('Printer:updatestatus[%s] Exception' % (self.name))
			self.snmpvalue = ''

		if self.snmpvalue == '':
			self.snmpstatus = SNMPStatus.NOTAVAILABLE
                        self.snmpinfo = 'Not Available, check if powered off or not plugged in'
		elif re.match(r'READY', self.snmpvalue):
			self.snmpstatus = SNMPStatus.READY
                        self.snmpinfo = 'Ready'
		elif re.match(r'COVER OPEN', self.snmpvalue):
			self.snmpstatus = SNMPStatus.COVEROPEN
                        self.snmpinfo = 'Printer Cover Open, close cover'
		elif re.match(r'ERROR', self.snmpvalue):
			self.snmpstatus = SNMPStatus.ERROR
                        self.snmpinfo = 'Error, check if jammed or out of labels'
		else:
			self.snmpstatus = SNMPStatus.UNKNOWN
                        self.snmpinfo = 'Unknown'

		#print('Printer:updatestatus[%s]: snmpvalue: %s snmpstatus: %s' % (self.name, self.snmpvalue, self.snmpstatus))
		if oldstatus != self.snmpstatus:
			print('Printer:updatestatus[%s]: %s %s'  % (self.name, getTimeNow(), self.snmpstatus.name))

	# add a print job to the print jobs queue
	#
	def add(self, pool, data):
		self.printjobs.append(Job(pool, data))
		return

	def status(self):
		print('value: %s' % status.value)
		return self.status

	# check if there are jobs queued to this printer and we are currently active
	#
	def checkforjobs(self):
		if len(self.printjobs) == 0:
			#print('Printer:checkforjobs[%s] status: %s snmp: %s jobs: %s NO JOBS' % (self.name, self.status, self.snmpstatus, len(self.printjobs)))
			return False
		if self.snmpstatus != SNMPStatus.READY:
			#print('Printer:checkforjobs[%s] status: %s snmp: %s jobs: %s SNMP NOT READY' % (self.name, self.status, self.snmpstatus, len(self.printjobs)))
			return False

		if self.sending:
			#print('Printer:checkforjobs[%s] status: %s snmp: %s jobs: %s Already Sending' % (self.name, self.status, self.snmpstatus, len(self.printjobs)))
			return False

		#print('Printer:checkforjobs[%s] status: %s snmp: %s jobs: %s HAVE JOBS' % (self.name, self.status, self.snmpstatus, len(self.printjobs)))

		# get current job and make a copy for working with
		self.currentjob = self.printjobs.pop(0)
		#print('Printer:checkforjobs[%s] job: %s' % (self.name, self.currentjob))
		#self.senddata = list(self.currentjob.data)
		#print('Printer:checkforjobs[%s] data: %s' % (self.name, self.senddata))
		self.sending = True

		return True

	def getJobData(self):
		return list(self.currentjob.data)

	def finished(self, flag):
		self.sending = False
		#print('Printer:finished: %s' % (self))
		job = self.currentjob
		self.currentjob = None
		#print('Printer:finished: currentjob: %s' % (job))
		pool = job.pool
		#print('Printer:finished: pool: %s' % (pool))
		if not flag:
			pool.recv(job.data)

	def __repr__(self):
		return "Printer[%s] status: %s snmpstatus: %s printjobs: %d\n" % (
			self.name, self.status, self.snmpstatus, len(self.printjobs))



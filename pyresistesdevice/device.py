# -*- coding: utf-8 -*-
'''
    pyresistesdevice.device
    -----------------------

    Allows data query from an electro-static resistivimeter device developped by UMR7619-Metis laboratory

    :copyright: Copyright 2015 Lionel Darras and contributors, see AUTHORS.
    :license: GNU GPL v3.

'''
from datetime import datetime
from pylink import link_from_url
from math import sqrt
import msvcrt
import time
import csv

from .logger import LOGGER
from .utils import (retry, bytes_to_hex, hex_to_bytes,
                    is_bytes, is_float, is_integer)
from .compat import stdout


class BadConfigParamException(Exception):
    '''No valid command.'''
    value = __doc__


class BadAckException(Exception):
    '''No valid acknowledgement.'''
    def __str__(self):
        return self.__doc__


class BadFlushException(Exception):
    '''Not possible to flush buffer.'''
    def __str__(self):
        return self.__doc__


class ResistESDevice(object):
    '''Communicates with the board by sending commands, reads the binary
    data and parsing it into usable scalar values.

    :param link: A `PyLink` connection.
    '''

    INJVOLT_MIN = 16.55
    INJVOLT_MAX = 196.51
    INJFREQ_MIN = 0
    INJFREQ_MAX = 62499
    CONFIGFRAME_LENGTH = 10
    CONFIGRESPFRAME_LENGTH = CONFIGFRAME_LENGTH + 1
    UX_MAX = 255        # 2^8 - 1
    FX_MAX = 33554431   # 2^25 - 1
    IX_MAX = 127        # 2^7 - 1
    TX_MAX = 16383      # 2^14 - 1
    RECFRAME_MAXSIZE = 1000
    MEASUREFRAME_MINLENGTH = 14
    POTENTIALVALUE_LENGTH = 4
    REQUESTMEASURE_CMD = b'\x80'
    RI = 110
    DATEFIELD = "date"
    COMMONFIELDS_LIST = ["count", "rec. batt. voltage(V)", "em. batt. voltage(V)", "phase current(mA)", "quad. current(mA)"]
    POTENTIALFIELDS_LIST = ["phase potential(mV) (ch%d)", "quad. potential(mV) (ch%d)"]
    RESISTIVITYFIELDS_LIST = ["phase resistivity(kOhm.m) (ch%d)", "quad. resistivity(kOhm.m) (ch%d)"]

    def __init__(self, link):
        self.link = link
        self.link.open()
        self.recframe=[]    # reception frame empty
        self.voltage = 0
        self.frequency = 0
        self.impuls_nb = 0
        self.channels_nb = 0
        self.integration_nb = 0
        

    @classmethod
    def from_url(cls, url, timeout=10):
        ''' Get device from url.

        :param url: A `PyLink` connection URL.
        :param timeout: Set a read timeout value.
        '''
        link = link_from_url(url)
        link.settimeout(timeout)
        return cls(link)


    @retry(tries=3, delay=0.5)
    def send(self, data, wait_ack=None, timeout=None):
        '''Sends data to device.

         :param data: Can be a byte array or an ASCII command. If this is
            the case for an ascii command, a <LF> will be added.

         :param wait_ack: If `wait_ack` is not None, the function must check
            that acknowledgement is the one expected.
         :param timeout: Define timeout when reading ACK from link
         '''
        if is_bytes(data):
            LOGGER.info("try send : %s" % bytes_to_hex(data))
            self.link.write(data)
        elif is_integer(data):
            LOGGER.info("try send : %02X" % data)
            self.link.write(chr(data))
        else:
            LOGGER.info("try send : %s" % data)
            self.link.write("%s" % data)
        if wait_ack is None:
            return True
        ack = self.link.read(len(wait_ack), timeout=timeout)
        if wait_ack == ack:
            LOGGER.info("Check ACK: OK (%s)" % (repr(ack)))
            return True
        LOGGER.error("Check ACK: BAD (%s != %s)" % (repr(wait_ack), repr(ack)))
        raise BadAckException()


    def receive(self, size=None, timeout=None):
        ackframe = self.link.read(size, timeout=timeout)
        return ackframe

    def flush(self, flushtimeout=30):
        ''' Flush the reception buffer.
        
         :param flushtimeout: Define timeout for flushing, if there is still
         data in the reception buffer after flushtimeout seconds, generate an error.
        
        '''
        begin = time.time()
        while (1):
            buffer = self.receive(timeout=0.1)
            if (len(buffer) == 0):
                return
            #break after wait sec
            if time.time() - begin > flushtimeout:
                break
        LOGGER.error("Flushing Reception Buffer: TOO LONG")
        raise BadFlushException()


    def setconfig(self, voltage, frequency, impuls_nb, channels_nb, integration_nb, timeout=None, flushtimeout=30):
        '''Sends configuration to device. Return True if acknowledge received, generate an error else.

         :param voltage: Injection signal voltage, V (between INJVOLT_MIN and INJVOLT_MAX)

         :param frequency: Injection signal frequency, kHz (between INJFREQ_MIN and INJFREQ_MAX)

         :param impuls_nb: external impulsions number triggering measure

         :param channels_nb: channels number to measure

         :param integration_nb: integration constant, number of values transmitted at computer in a second

         :param timeout: Define timeout when reading ACK from link
         
         :param flushtimeout: Define timeout for flushing, if there is still
         data in the reception buffer after flushtimeout seconds, generate an error.
        
         '''

        LOGGER.info("check parameters : %f %f %d %d %d" % (voltage, frequency, impuls_nb, channels_nb, integration_nb))
        configframe = self._to_configframe( voltage, frequency, impuls_nb, channels_nb, integration_nb)

        LOGGER.info("flush reception buffer before sending command ...")
        self.flush(flushtimeout=flushtimeout)                          
                
        self.send(configframe, timeout=timeout)          # send config frame
        
        time.sleep(1)                                    # waiting for 1 second before reading  

        ackframe = self.receive( self.CONFIGRESPFRAME_LENGTH, timeout=timeout)

        ack, run, boardid = self._verifconfigack(ackframe, configframe)
        if (ack == True) :
            LOGGER.info("Check ACK: OK (%s, %d, %d)" % (repr(ack), run, boardid))
            self.voltage = voltage
            self.frequency = frequency
            self.impuls_nb = impuls_nb
            self.channels_nb = channels_nb
            self.integration_nb = integration_nb
            return True
        LOGGER.error("Check ACK: BAD (%s, %s)" % (repr(configframe), repr(ackframe)))
        raise BadAckException()



    def updatereceptionframe(self, size=None, timeout=None):
        ''' update reception frame by getting bytes received.
        The maximum amount of data to be received at once
        is specified by `size`.
        '''
        bytes = self.link.read(size=size, timeout=timeout)
        if (len(bytes) > 0):
            for l in range(len(bytes)):
                self.recframe.append(bytes[l])
        

        
    def sendmeasuresrequest(self):
        ''' send request to get measures.
        '''
        self.link.write(self.REQUESTMEASURE_CMD)



    def getrawmeasures(self):
        ''' get raw measures if possible. Returns result = True if measure frame received, then :
        all fields received in the frame, coded in bytes, word ou double word.
        '''
        result, count, recbatvoltage, embatvoltage, phasecurrent, quadcurrent, phasepotentialarray, quadpotentialarray = self._from_measureframe(self.recframe)
        if (result == True):
            self.recframe.clear()
            LOGGER.info("Get raw measures: (%d, %d, %d, %d, %d, %d)" % (result, count, recbatvoltage, embatvoltage, phasecurrent, quadcurrent))
        for l in range(len(phasepotentialarray)):            
            LOGGER.info("Potential[%d] :(%d, %d)" % (l, phasepotentialarray[l], quadpotentialarray[l]))
        return result, count, recbatvoltage, embatvoltage, phasecurrent, quadcurrent, phasepotentialarray, quadpotentialarray
    


    def getrealmeasures(self):
        ''' get real measures if possible. Returns result = True if measure frame received, then :
        all fields received in the frame, decoded in integers or floats.
        '''
        result, count, recbatvoltage, embatvoltage, phasecurrent, quadcurrent, phasepotentialarray, quadpotentialarray = self.getrawmeasures()
        phasepotentialrealarray = []
        quadpotentialrealarray = []
        potentialrealarray = []
        phasecurrentrealvalue = 0
        quadcurrentrealvalue = 0
        recrealbatvoltage = (18.3*recbatvoltage)/16383
        emrealbatvoltage = (18.3*embatvoltage)/16383
        if (result == 1):
            phasecurrentrealvalue = self.tocurrentrealvalue(phasecurrent)
            quadcurrentrealvalue = self.tocurrentrealvalue(quadcurrent)
            currentrealvalue = self.fromphaseandquadrature(phasecurrentrealvalue, quadcurrentrealvalue)
            for l in range(len(phasepotentialarray)):
                phasepotentialrealarray.append(self.topotentialrealvalue(phasepotentialarray[l]))
                quadpotentialrealarray.append(self.topotentialrealvalue(quadpotentialarray[l]))
                potentialrealarray.append(self.fromphaseandquadrature(phasepotentialrealarray[l],quadpotentialrealarray[l]))
        
        return result, count, recrealbatvoltage, emrealbatvoltage, phasecurrentrealvalue, quadcurrentrealvalue, phasepotentialrealarray, quadpotentialrealarray

    

    def getallmeasures(self):
        ''' get all measures if possible. Returns result = True if measure frame received, then :
        all fields received in the frame, decoded in integers or floats, and fields calculated from others fields.
        '''
        result, count, recbatvoltage, embatvoltage, phasecurrent, quadcurrent, phasepotentialarray, quadpotentialarray = self.getrawmeasures()
        phasepotentialrealarray = []
        quadpotentialrealarray = []
        potentialrealarray = []
        phaseresistivityarray = []
        quadresistivityarray = []
        phasecurrentrealvalue = 0
        quadcurrentrealvalue = 0
        recrealbatvoltage = (18.3*recbatvoltage)/16383
        emrealbatvoltage = (18.3*embatvoltage)/16383
        if (result == 1):
            phasecurrentrealvalue = self.tocurrentrealvalue(phasecurrent)
            quadcurrentrealvalue = self.tocurrentrealvalue(quadcurrent)
            currentrealvalue = self.fromphaseandquadrature(phasecurrentrealvalue, quadcurrentrealvalue)
            for l in range(len(phasepotentialarray)):
                phasepotentialrealarray.append(self.topotentialrealvalue(phasepotentialarray[l]))
                quadpotentialrealarray.append(self.topotentialrealvalue(quadpotentialarray[l]))
                potentialrealarray.append(self.fromphaseandquadrature(phasepotentialrealarray[l],quadpotentialrealarray[l]))
                phaseresistivity, quadresistivity = self.toresistivityvalue(phasecurrentrealvalue, quadcurrentrealvalue, phasepotentialrealarray[l], quadpotentialrealarray[l])
                phaseresistivityarray.append(phaseresistivity)
                quadresistivityarray.append(quadresistivity)
        
        return result, count, recrealbatvoltage, emrealbatvoltage, phasecurrentrealvalue, quadcurrentrealvalue, phasepotentialrealarray, quadpotentialrealarray, phaseresistivityarray, quadresistivityarray


    def getallfieldnames(self):
        ''' get all field names,
        the number of field names depends on the channel nb configured.
        '''
        fieldnames = self.COMMONFIELDS_LIST
        for i in range(self.channels_nb):
            for n in range(len(self.POTENTIALFIELDS_LIST)):
                fieldnames.append(self.POTENTIALFIELDS_LIST[n]%i)
            for n in range(len(self.RESISTIVITYFIELDS_LIST)):
                fieldnames.append(self.RESISTIVITYFIELDS_LIST[n]%i)
        return fieldnames
    

    def getrealfieldnames(self):
        ''' get real field names,
        the number of field names depends on the channel nb configured.
        '''
        fieldnames = self.COMMONFIELDS_LIST
        for i in range(self.channels_nb):
            for n in range(len(self.POTENTIALFIELDS_LIST)):
                fieldnames.append(self.POTENTIALFIELDS_LIST[n]%i)
        return fieldnames
    

    def acquiremeasures(self, output=stdout, delim=';', stdoutdisplay=False, datetimedisplay=False):
        ''' acquire all measures (getted by COM port and calculated values),
        saves the data in a file if output != stdout, and display
        in the prompt window if stdoutdisplay == True.
        
        :param output: Filename where output is written (default: standard out)
        
        :param delim: CSV char delimiter (default: ";")
        
        :param stdoutdisplay: Display on the standard out if defined output is a file

        :param datetimedisplay: Display and save date and time if True
        
        '''

        csvlines = []                                                           # construction of first line with fields names
        if (datetimedisplay==True):
            csvline = [self.DATEFIELD] + self.COMMONFIELDS_LIST
        else:
            csvline = self.COMMONFIELDS_LIST
        for n in range(self.channels_nb):
            for i in range(len(self.POTENTIALFIELDS_LIST)):                
                csvline.append(self.POTENTIALFIELDS_LIST[i]%n)
            for i in range(len(self.POTENTIALFIELDS_LIST)):                
                csvline.append(self.RESISTIVITYFIELDS_LIST[i]%n)

        for j in range(len(csvline)):
            if (j==0):
                todisplay = csvline[j]
            else:
                todisplay = todisplay + delim + csvline[j]
                
        output.write(todisplay + '\n')
        
        if (stdoutdisplay == True) and(output!=stdout):
            stdout.write(todisplay + '\n')
            
        csvlines.append(csvline)
        
        while (1) :
            try:
                self.updatereceptionframe(None,0.1)                             # update reception frame if needed
                                                                                # get all measures
                result, count, recrealbatvoltage, emrealbatvoltage, phasecurrentrealvalue, quadcurrentrealvalue, phasepotentialrealarray, quadpotentialrealarray, phaseresistivityarray, quadresistivityarray = self.getallmeasures()

                if result == True:                                              # if measure
                    csvline = []
                    todisplay=""
                    if (datetimedisplay==True):
                        dt = datetime.utcnow()                                  # get date and time
                        csvline.append(dt)
                        todisplay = str(dt) + delim
                    csvline.append(count)
                    todisplay = todisplay + "%d"%count
                    csvline.append(recrealbatvoltage)
                    todisplay = todisplay + delim + "%.1f"%recrealbatvoltage
                    csvline.append(emrealbatvoltage)
                    todisplay = todisplay + delim + "%.1f"%emrealbatvoltage
                    csvline.append(phasecurrentrealvalue)
                    todisplay = todisplay + delim + "%f"%phasecurrentrealvalue
                    csvline.append(quadcurrentrealvalue)
                    todisplay = todisplay + delim + "%f"%quadcurrentrealvalue
                    for n in range(self.channels_nb):
                        csvline.append(phasepotentialrealarray[n])
                        todisplay = todisplay + delim + "%f"%phasepotentialrealarray[n]
                        csvline.append(quadpotentialrealarray[n])
                        todisplay = todisplay + delim + "%f"%quadpotentialrealarray[n]
                        csvline.append(phaseresistivityarray[n])
                        todisplay = todisplay + delim + "%f"%phaseresistivityarray[n]
                        csvline.append(quadresistivityarray[n])
                        todisplay = todisplay + delim +"%f"%quadresistivityarray[n]

                    output.write(todisplay + '\n')
                    if (stdoutdisplay == True) and (output!=stdout):
                        stdout.write(todisplay + '\n')

                    csvlines.append(csvline)

                if msvcrt.kbhit():                                              # key press detection
                    c = msvcrt.getch()
                    if ord(c) != None:
                        self.sendmeasuresrequest()                              # send manual measure command
                        
            except KeyboardInterrupt:                                           # 'Ctrl' + 'C' detected
                break            


        
    def topotentialrealvalue(self, potentialcodedvalue):
        ''' converts potential coded value (4 bytes) and returns its real value in mV,
        output = (potentialcodedvalue*5000)/pow(2, 28)

        :param potentialcodedvalue: Potential value coded on 4 bytes
        
        '''
        potentialrealvalue = (potentialcodedvalue*5000)/pow(2, 28)
        LOGGER.info("Convert to potential real value : %d -> %f" % (potentialcodedvalue, potentialrealvalue))
        return potentialrealvalue


    def fromphaseandquadrature(self, phasevalue, quadvalue):
        ''' calculates and returns value from its phase and quadrature components,
        output = sqrt(pow(phasevalue,2) + pow(quadvalue,2))

        :param phasevalue: Phase part of value.

        :param quadvalue: Quadrature part of value
        
        '''
        value = sqrt(pow(phasevalue,2) + pow(quadvalue,2))
        LOGGER.info("Convert from phase and quadrature : (%f,%f) -> %f" % (phasevalue, quadvalue, value))
        return value



    def tocurrentrealvalue(self, currentcodedvalue):
        ''' convert current coded value (4 bytes) and returns its real value in mA,
        
        output = (currentcodedvalue*5000000)/(RI*pow(2, 28))

        :param currentcodedvalue: Current value coded on 4 bytes
        
        '''
        currentrealvalue = (currentcodedvalue*5000000)/(self.RI*pow(2, 28))
        LOGGER.info("Convert to current real value : %d -> %f" % (currentcodedvalue, currentrealvalue))
        return currentrealvalue



    def toresistivityvalue(self, phasecurrentscalarvalue, quadcurrentscalarvalue, phasepotentialscalarvalue, quadpotentialscalarvalue):
        ''' calculate and returns resistivity value (Ohms.m) from phase & quadrature scalar current and potential,
        
        outputs :
        
            phaseresistivityvalue = ((phasepotentialscalarvalue*phasecurrentscalarvalue) +
                                    (quadpotentialvalue*quadcurrentscalarvalue))/(pow(phasecurrentscalarvalue,2) + pow(quadcurrentscalarvalue,2))

            quadresistivityvalue = ((quadpotentialscalarvalue*phasecurrentscalarvalue) -
                                   (phasepotentialscalarvalue*quadcurrentscalarvalue))/(pow(phasecurrentscalarvalue,2) + pow(quadcurrentscalarvalue,2))
        
        :param phasecurrentscalarvalue: Phase current scalar value
        
        :param quadcurrentscalarvalue: Quadrature current scalar value
        
        :param phasepotentialscalarvalue: Phase potential scalar value
        
        :param quadpotentialscalarvalue: Phase potential scalar value
        
        '''
        phaseresistivityvalue = 1000*((phasepotentialscalarvalue*phasecurrentscalarvalue) + (quadpotentialscalarvalue*quadcurrentscalarvalue))/(pow(phasecurrentscalarvalue,2) + pow(quadcurrentscalarvalue,2))
        quadresistivityvalue = 1000*((quadpotentialscalarvalue*phasecurrentscalarvalue) - (phasepotentialscalarvalue*quadcurrentscalarvalue))/(pow(phasecurrentscalarvalue,2) + pow(quadcurrentscalarvalue,2))
        LOGGER.info("Calculate resistivities(Ohms.m) (%f,%f) from potential (%f, %f) and current(%f, %f)" % (phaseresistivityvalue, quadresistivityvalue, phasepotentialscalarvalue, quadpotentialscalarvalue, phasecurrentscalarvalue, quadcurrentscalarvalue))
        return phaseresistivityvalue, quadresistivityvalue



    def _ismeasureframevalid(self, measureframe):
        ''' verify if measure frame is valid.
        '''
        # verify if good length of frame
        if (len(measureframe) == 0):
            return False
        if (len(measureframe) != (self.MEASUREFRAME_MINLENGTH + self.channels_nb*2*self.POTENTIALVALUE_LENGTH)):
            LOGGER.info("Check Measure Frame Length: BAD (%d, %d)" % (len(measureframe), (self.MEASUREFRAME_MINLENGTH + self.channels_nb*2*self.POTENTIALVALUE_LENGTH)))
            return False
        LOGGER.info("Check Measure Frame Length: OK (%d)" % (len(measureframe)))

        #verify if each byte of frame has the good value of higher bit
        # measure counter value
        if not self._isbit7valueat1(measureframe[0]):       # byte 0 of measure frame >= 0x80
            LOGGER.info("Check Measure Frame Byte 0: BAD (%02X)" % (measureframe[0]))
            return False
        if not self._isbit7valueat1(measureframe[1]):       # byte 1 of measure frame >= 0x80
            LOGGER.info("Check Measure Frame Byte 1: BAD (%02X)" % (measureframe[1]))
            return False
        # reception battery voltage
        if not self._isbit7valueat1(measureframe[2]):       # byte 2 of measure frame >= 0x80
            LOGGER.info("Check Measure Frame Byte 2: BAD (%02X)" % (measureframe[2]))
            return False
        if not self._isbit7valueat0(measureframe[3]):       # byte 3 of measure frame < 0x80
            LOGGER.info("Check Measure Frame Byte 3: BAD (%02X)" % (measureframe[3]))            
            return False
        # emission battery voltage
        if not self._isbit7valueat1(measureframe[4]):       # byte 4 of measure frame >= 0x80
            LOGGER.info("Check Measure Frame Byte 4: BAD (%02X)" % (measureframe[4]))
            return False
        if not self._isbit7valueat0(measureframe[5]):       # byte 5 of measure frame < 0x80
            LOGGER.info("Check Measure Frame Byte 5: BAD (%02X)" % (measureframe[5]))
            return False
        # phase current value
        if not self._isbit7valueat1(measureframe[6]):       # byte 6 of measure frame >= 0x80
            LOGGER.info("Check Measure Frame Byte 6: BAD (%02X)" % (measureframe[6]))
            return False
        if not self._isbit7valueat0(measureframe[7]):       # byte 7 of measure frame < 0x80
            LOGGER.info("Check Measure Frame Byte 7: BAD (%02X)" % (measureframe[7]))
            return False
        if not self._isbit7valueat0(measureframe[8]):       # byte 8 of measure frame < 0x80
            LOGGER.info("Check Measure Frame Byte 8: BAD (%02X)" % (measureframe[8]))
            return False
        if not self._isbit7valueat0(measureframe[9]):       # byte 9 of measure frame < 0x80
            LOGGER.info("Check Measure Frame Byte 9: BAD (%02X)" % (measureframe[9]))
            return False
        # quadrature current value
        if not self._isbit7valueat1(measureframe[10]):       # byte 10 of measure frame >= 0x80
            LOGGER.info("Check Measure Frame Byte 10: BAD (%02X)" % (measureframe[10]))
            return False
        if not self._isbit7valueat0(measureframe[11]):       # byte 11 of measure frame < 0x80
            LOGGER.info("Check Measure Frame Byte 11: BAD (%02X)" % (measureframe[11]))
            return False
        if not self._isbit7valueat0(measureframe[12]):       # byte 12 of measure frame < 0x80
            LOGGER.info("Check Measure Frame Byte 12: BAD (%02X)" % (measureframe[12]))
            return False
        if not self._isbit7valueat0(measureframe[13]):       # byte 13 of measure frame < 0x80
            LOGGER.info("Check Measure Frame Byte 13: BAD (%02X)" % (measureframe[13]))
            return False
        for i in range(self.channels_nb):
            # phase voltage value
            if not self._isbit7valueat1(measureframe[self.MEASUREFRAME_MINLENGTH+i*4]):       # byte of measure frame >= 0x80
                LOGGER.info("Check Measure Frame Byte %d: BAD (%02X)" % (self.MEASUREFRAME_MINLENGTH+i*4, measureframe[self.MEASUREFRAME_MINLENGTH+i*4]))
                return False
            if not self._isbit7valueat0(measureframe[self.MEASUREFRAME_MINLENGTH+i*4+1]):       # byte of measure frame < 0x80
                LOGGER.info("Check Measure Frame Byte %d: BAD (%02X)" % (self.MEASUREFRAME_MINLENGTH+i*4+1, measureframe[self.MEASUREFRAME_MINLENGTH+i*4+1]))
                return False
            if not self._isbit7valueat0(measureframe[self.MEASUREFRAME_MINLENGTH+i*4+2]):       # byte of measure frame < 0x80
                LOGGER.info("Check Measure Frame Byte %d: BAD (%02X)" % (self.MEASUREFRAME_MINLENGTH+i*4+2, measureframe[self.MEASUREFRAME_MINLENGTH+i*4+2]))
                return False
            if not self._isbit7valueat0(measureframe[self.MEASUREFRAME_MINLENGTH+i*4+3]):       # byte of measure frame < 0x80
                LOGGER.info("Check Measure Frame Byte %d: BAD (%02X)" % (self.MEASUREFRAME_MINLENGTH+i*4+3, measureframe[self.MEASUREFRAME_MINLENGTH+i*4+3]))
                return False
            # quadrature voltage value
            if not self._isbit7valueat1(measureframe[self.MEASUREFRAME_MINLENGTH+i*4+4]):       # byte of measure frame >= 0x80
                LOGGER.info("Check Measure Frame Byte %d: BAD (%02X)" % (self.MEASUREFRAME_MINLENGTH+i*4+4, measureframe[self.MEASUREFRAME_MINLENGTH+i*4+4]))
                return False
            if not self._isbit7valueat0(measureframe[self.MEASUREFRAME_MINLENGTH+i*4+5]):       # byte of measure frame < 0x80
                LOGGER.info("Check Measure Frame Byte %d: BAD (%02X)" % (self.MEASUREFRAME_MINLENGTH+i*4+5, measureframe[self.MEASUREFRAME_MINLENGTH+i*4+5]))
                return False
            if not self._isbit7valueat0(measureframe[self.MEASUREFRAME_MINLENGTH+i*4+6]):       # byte of measure frame < 0x80
                LOGGER.info("Check Measure Frame Byte %d: BAD (%02X)" % (self.MEASUREFRAME_MINLENGTH+i*4+6, measureframe[self.MEASUREFRAME_MINLENGTH+i*4+6]))
                return False
            if not self._isbit7valueat0(measureframe[self.MEASUREFRAME_MINLENGTH+i*4+7]):       # byte of measure frame < 0x80
                LOGGER.info("Check Measure Frame Byte %d: BAD (%02X)" % (self.MEASUREFRAME_MINLENGTH+i*4+7, measureframe[self.MEASUREFRAME_MINLENGTH+i*4+7]))
                return False            
        return True
        


    def _isbit7valueat1(self, byte):
        ''' verify is bit 7 value is 1. '''
        return ((byte & 0x80) == 0x80)



    def _isbit7valueat0(self, byte):
        ''' verify is bit 7 value is 0. '''
        return ((byte & 0x80) == 0x00)



    def _from_measureframe(self, measureframe):
        ''' from measure frame, returns coded values of measures.
        
        Measure count value (2 bytes)

        Byte 0 : 1  D6  D5  D4  D3  D2  D1  D0      
        
        Byte 1 : 1 D13 D12 D11 D10  D9  D8  D7
        
        Reception battery voltage (2 bytes)

        Byte 2 : 1  D6  D5  D4  D3  D2  D1  D0      
        
        Byte 3 : 0 D13 D12 D11 D10  D9  D8  D7
        
        Emission battery voltage (2 bytes)

        Byte 4 : 1  D6  D5  D4  D3  D2  D1  D0      
        
        Byte 5 : 0 D13 D12 D11 D10  D9  D8  D7
        
        Phase current value (4 bytes)

        Byte 6 : 1  D6  D5  D4  D3  D2  D1  D0      
        
        Byte 7 : 0 D13 D12 D11 D10  D9  D8  D7
        
        Byte 8 : 0 D20 D19 D18 D17 D16 D15 D14
        
        Byte 9 : 0 D27 D26 D25 D24 D23 D22 D21
        
        Quadrature current value (4 bytes)

        Byte 10: 1  D6  D5  D4  D3  D2  D1  D0      
        
        Byte 11: 0 D13 D12 D11 D10  D9  D8  D7
        
        Byte 12: 0 D20 D19 D18 D17 D16 D15 D14

        Byte 13: 0 D27 D26 D25 D24 D23 D22 D21

        ... For X between 0 and N channels number                                       

        Phase potential value channel X (4 bytes)

        Byte ..: 1  D6  D5  D4  D3  D2  D1  D0      

        Byte ..: 0 D13 D12 D11 D10  D9  D8  D7

        Byte ..: 0 D20 D19 D18 D17 D16 D15 D14

        Byte ..: 0 D27 D26 D25 D24 D23 D22 D21

        Quadrature potential value channel X (4 bytes)

        Byte ..: 1  D6  D5  D4  D3  D2  D1  D0      

        Byte ..: 0 D13 D12 D11 D10  D9  D8  D7

        Byte ..: 0 D20 D19 D18 D17 D16 D15 D14

        Byte ..: 0 D27 D26 D25 D24 D23 D22 D21

        ...

        GPS Frame (not used at the moment)

        Byte ..: 0   X   X   X   X   X   X   X      

        '''

        if not self._ismeasureframevalid(measureframe):
            return False, 0, 0, 0, 0, 0, [], []
            
        # measure count value
        count = (measureframe[0] & 0x7F) + ((measureframe[1] & 0x7F) << 7)

        # reception battery voltage
        recbatvoltage = (measureframe[2] & 0x7F) + ((measureframe[3] & 0x7F) << 7)

        # emission battery voltage
        embatvoltage = (measureframe[4] & 0x7F) + ((measureframe[5] & 0x7F) << 7)

        # phase current value
        phasecurrent = (measureframe[6] & 0x7F) + ((measureframe[7] & 0x7F) << 7) + ((measureframe[8] & 0x7F) << 14) + ((measureframe[9] & 0x7F) << 21)
        if (phasecurrent > pow(2,27)):  # > 2^27
            phasecurrent -= pow(2,28)   # - 2^28
        
        # quadrature current value
        quadcurrent = (measureframe[10] & 0x7F) + ((measureframe[11] & 0x7F) << 7) + ((measureframe[12] & 0x7F) << 14) + ((measureframe[13] & 0x7F) << 21)
        if (quadcurrent > pow(2,27)):  # > 2^27
            quadcurrent -= pow(2,28)   # - 2^28

        phasevoltagearray = []
        quadvoltagearray = []
        # for each channel
        for i in range(self.channels_nb):
            # add phase potential value
            phasevoltage = (measureframe[self.MEASUREFRAME_MINLENGTH+i*2] & 0x7F) + ((measureframe[self.MEASUREFRAME_MINLENGTH+i*2+1] & 0x7F) << 7) + \
                           ((measureframe[self.MEASUREFRAME_MINLENGTH+i*2+2] & 0x7F) << 14) + ((measureframe[self.MEASUREFRAME_MINLENGTH+i*2+3] & 0x7F) << 21)
            if (phasevoltage > pow(2,27)):  # > 2^27
                phasevoltage -= pow(2,28)   # - 2^28
            phasevoltagearray.append(phasevoltage)
            # add quadrature potential value
            quadvoltage = (measureframe[self.MEASUREFRAME_MINLENGTH+i*2+4] & 0x7F) + ((measureframe[self.MEASUREFRAME_MINLENGTH+i*2+5] & 0x7F) << 7) + \
                          ((measureframe[self.MEASUREFRAME_MINLENGTH+i*2+6] & 0x7F) << 14) + ((measureframe[self.MEASUREFRAME_MINLENGTH+i*2+7] & 0x7F) << 21)
            if (quadvoltage > pow(2,27)):  # > 2^27
                quadvoltage -= pow(2,28)   # - 2^28
            quadvoltagearray.append(quadvoltage)

        return True, count, recbatvoltage, embatvoltage, phasecurrent, quadcurrent, phasevoltagearray, quadvoltagearray



    def _verifconfigack(self, ackframe, configframe):
        ''' verify if ackframe correspond to configframe response,
        if it's ok, returns True, run(=0 if device stopped), boardid(voard identifier).

        :param ackframe: Acknowledgement frame.

        :param configframe: Configuration frame.
        
        '''

        if (len(ackframe) != (len(configframe) + 1)):
            return False, 0, 0
        
        # verify come back of configuration frame
        for l in range(len(configframe)):
            if (ackframe[l] != configframe[l]):
                return False, 0, 0

        # decode run and board identifiant      0 Id5 Id4 Id3 Id2 Id1 Id0 Fct0
        run = (ackframe[-1] & 0x01)             # Fct0
        boardid = (ackframe[-1] & 0x7E) >> 1    # Id[5:0]
        return True, run, boardid



    def _to_configframe(self, voltage, frequency, impuls_nb, channels_nb, integration_nb):
        '''from configuration parameters, returns the configuration frame to send to the device.
        
        Ux, Injection signal voltage

        Byte 0 : 1  U5  U4  U3  U2  U1  U0   1      
        
        Byte 1 : 0   0   0   0   0   0  U7  U6

        Fx, Injection signal frequency
        
        Byte 2 : 0  F6  F5  F4  F3  F2  F1  F0      
        
        Byte 3 : 0 F13 F12 F11 F10  F9  F8  F7
        
        Byte 4 : 0 F20 F19 F18 F17 F16 F15 F14
        
        Byte 5 : 0   0   0   0 F24 F23 F22 F21

        Ix, External impulsions
        
        Byte 6 : 0  I6  I5  I4  I3  I2  I1  I0      

        Vx, Channels number
        
        Byte 7 : 0  V6  V5  V4  V3  V2  V1  V0      

        Tx, Integration constant
        
        Byte 8 : 0  T6  T5  T4  T3  T2  T1  T0      

        Byte 9 : 0 T13 T12 T11 T10  T9  T8  T7

        :param voltage: Injection signal voltage, V (between INJVOLT_MIN and INJVOLT_MAX)

        :param frequency: Injection signal frequency, Hz (between INJFREQ_MIN and INJFREQ_MAX)

        :param impuls_nb: External impulsions number triggering measure

        :param channels_nb: Channels number to measure

        :param integration_nb: Integration constant, number of values transmitted at computer in a second
         
        '''

        # voltage operation
        if (not is_float(voltage)):
            LOGGER.error("Check voltage parameter: NOT A FLOAT")
            raise BadConfigParamException()
        
        if (voltage <= self.INJVOLT_MAX) and (voltage >= self.INJVOLT_MIN):
            LOGGER.info("Check voltage parameter: OK (%f <= %f <= %f)" % (self.INJVOLT_MIN, voltage, self.INJVOLT_MAX))
        else:
            LOGGER.info("Check voltage parameter: BAD VALUE (%f <> %f <> %f)" % (self.INJVOLT_MIN, voltage, self.INJVOLT_MAX))
            raise BadConfigParamException()
        
        Ux = round((256*((900/voltage)-0.08-4.5))/50)
        if (Ux > self.UX_MAX):
            LOGGER.info("Check voltage parameter: BAD CONVERSION (%f , %02X)" % (voltage, Ux))
            raise BadConfigParamException()
        LOGGER.info("Check voltage parameter: GOOD CONVERSION (%f, %02X)" % (voltage, Ux))

        # frequency    
        if (not is_float(frequency)):
            LOGGER.error("Check frequency parameter: NOT A FLOAT")
            raise BadConfigParamException()
        
        if (frequency <= self.INJFREQ_MAX) and (frequency >= self.INJFREQ_MIN):
            LOGGER.info("Check frequency parameter: OK (%f <= %f <= %f)" % (self.INJFREQ_MIN, frequency, self.INJFREQ_MAX))
        else:
            LOGGER.info("Check frequency parameter: BAD (%f <> %f <> %f)" % (self.INJFREQ_MIN, frequency, self.INJFREQ_MAX))
            raise BadConfigParamException()

        Fx = round(frequency * ((pow(2, 28))/500000))
        if (Fx > self.FX_MAX):
            LOGGER.info("Check frequency parameter: BAD CONVERSION (%f , %08X)" % (frequency, Fx))
            raise BadConfigParamException()
        LOGGER.info("Check frequency parameter: GOOD CONVERSION (%f, %08X)" % (frequency, Fx))

        # impulsion number
        if (not is_integer(impuls_nb)):
            LOGGER.error("Check impuls_nb parameter: NOT AN INTEGER")
            raise BadConfigParamException()

        if (impuls_nb <= self.IX_MAX):
            LOGGER.info("Check impuls_nb parameter: OK (%d <= %d)" % (impuls_nb, self.IX_MAX))
        else:
            LOGGER.info("Check impuls_nb parameter: BAD (%d <> %d)" % (impuls_nb, self.IX_MAX))
            raise BadConfigParamException()
        

        # channels number
        if (not is_integer(channels_nb)):
            LOGGER.error("Check channels_nb parameter: NOT AN INTEGER")
            raise BadConfigParamException()

        if (channels_nb <= self.UX_MAX):
            LOGGER.info("Check channels_nb parameter: OK (%d <= %d)" % (channels_nb, self.UX_MAX))
        else:
            LOGGER.info("Check channels_nb parameter: BAD (%d <> %d)" % (channels_nb, self.UX_MAX))
            raise BadConfigParamException()


        # integration constant
        if (not is_integer(integration_nb)):
            LOGGER.error("Check integration_nb parameter: NOT AN INTEGER")
            raise BadConfigParamException()

        if (integration_nb <= self.TX_MAX):
            LOGGER.info("Check integration_nb parameter: OK (%d <= %d)" % (integration_nb, self.TX_MAX))
        else:
            LOGGER.info("Check integration_nb parameter: BAD (%d <> %d)" % (integration_nb, self.TX_MAX))
            raise BadConfigParamException()


        # building to configuration frame
        config_frame = []
        config_frame.append(0x81 + ((Ux&0x003F)<<1))        # 1  U5  U4  U3  U2  U1  U0   1
        config_frame.append(((Ux&0x00C0)>>6))               # 0   0   0   0   0   0  U7  U6
        config_frame.append(Fx&0x0000007F)                  # 0  F6  F5  F4  F3  F2  F1  F0
        config_frame.append((Fx&0x00003F80)>>7)             # 0 F13 F12 F11 F10  F9  F8  F7
        config_frame.append((Fx&0x001FC000)>>14)            # 0 F20 F19 F18 F17 F16 F15 F14
        config_frame.append((Fx&0x0FE00000)>>21)            # 0   0   0   0 F24 F23 F22 F21
        config_frame.append(impuls_nb&0x7F)                 # 0  I6  I5  I4  I3  I2  I1  I0
        config_frame.append(channels_nb&0x7F)               # 0  V6  V5  V4  V3  V2  V1  V0
        config_frame.append(integration_nb&0x007F)          # 0  T6  T5  T4  T3  T2  T1  T0
        config_frame.append((integration_nb&0x3F80)>>7)     # 0 T13 T12 T11 T10  T9  T8  T7
        config_hexstring = "%02X %02X %02X %02X %02X %02X %02X %02X %02X %02X" % \
                        (config_frame[0], config_frame[1], config_frame[2], config_frame[3], config_frame[4], \
                         config_frame[5], config_frame[6], config_frame[7], config_frame[8], config_frame[9])
        LOGGER.info("Configuration frame (%d bytes): %s" % (len(config_frame), config_hexstring))

        config_bytesstring = hex_to_bytes(config_hexstring)
        return config_bytesstring


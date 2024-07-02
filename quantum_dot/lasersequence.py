import numpy as np
from .nvaverageprogram import NVAveragerProgram
import qickdawg as qd


def laser_sequence(config, reps=1, readout_integration_treg=1020):
    '''Sets laser PMOD to high without turning off

    Parameters
    ----------
    config : `.NVConfig`
        See `.LaserOn` for required attributes
    reps : int (optional, 1)
    readout_integration_treg (option, 3)

    Returns
    -------
    int
        integrated ADC value over time readout_integration_treg
    '''
    config.reps = reps
    config.readout_integration_treg = readout_integration_treg
    prog = LaserSequence(config)
    prog.acquire()



class DigitalOutput:
    sequence = []

    def __init__(self, pmod_ch, seq):
        self.pmod_ch = pmod_ch
        self.seq = seq
        
        # Convert list of tuples into list of lists
        self.seq = [list(t) for t in self.seq]

        # TODO - Convert pico seconds into clock cycles

        # Convert pulse widths into elapsed time and append channel to list
        time = 0
        for l in self.seq:
            l[0], time = time, time + l[0]
            l.append(pmod_ch)
        
        # End final pulse
        self.seq.append([time, 0, pmod_ch])

        # Add channel sequence to master sequence and sort in order of time
        [self.sequence.append(l) for l in self.seq]
        self.sequence.sort(key=lambda x: x[0])



class LaserSequence(NVAveragerProgram):
    """
    Class which creates a qickdawg program that will turn the laser controller
    to the on state without turning the laser controller of

    Parameters
    -----------
    soccfg
        instance of qick.QickConfig class
    cfg
        instance of qickdawg.NVConfiguration class with attributes
        .adc_cannel (required)
        .laser_gate_pmod(required)

    Methods
    -------
    acquire
        returns a single datapoint which may be used the PL intensity

    """

    def initialize(self):
        """
        Method that generates the assembly code that initializes the pulse sequence.
        For LaserOn this simply sets up the adc to integrate for self.cfg.readout_intregration_t#
        """
        self.declare_readout(ch=self.cfg.adc_channel,
                             freq=0,
                             length=self.cfg.readout_integration_treg,
                             sel="input")
        
        # self.seq = []
        # for i in range(len(self.sequence)):
        #     self.seq.append(qd.soccfg.us2cycles(self.sequence[i][0]/1e6))

        self.synci(400)  # give processor some time to configure pulses


    def body(self):
        '''
        Method that generates the assembly code that is looped over or repeated.
        For LaserOn this simply sets laser_gate_pmod to the high value
        '''

        out = 0
        trig_output = self.soccfg['tprocs'][0]['trig_output']

        for l in DigitalOutput.sequence: 
            time = l[0]
            state = l[1]
            bit_position = l[2]

            if state == 1:
                out |= (1 << bit_position)
            elif state == 0:
                out &= ~(1 << bit_position)

            print(bin(out), time)
            self.regwi(0, 31, out)
            self.seti(trig_output, 0, 31, time)
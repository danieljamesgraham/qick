import numpy as np
from .nvaverageprogram import NVAveragerProgram
import qickdawg as qd


def laser_toggle(config, sequence, reps=1, readout_integration_treg=1020):
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
    # sequence = [100,1000,10,10,100,100,200,0]
    config.reps = reps
    config.readout_integration_treg = readout_integration_treg
    prog = LaserToggle(config, sequence)
    prog.acquire()


class LaserToggle(NVAveragerProgram):
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

        for i in range(len(self.sequence)):
            self.sequence[i] = list(self.sequence[i])
            self.sequence[i][0] = qd.soccfg.us2cycles(self.sequence[i][0]/1e6)

        self.times = []
        self.widths = []

        for i in range(len(self.sequence) - 1):
            if self.sequence[i][1] == self.sequence[i+1][1]:
                print("Hello!")

        for i in range(len(self.sequence)):
            self.sequence[i] = tuple(self.sequence[i])


        print(self.sequence)

        if self.sequence[0][1] == 0:
            self.delay = self.sequence[0][0]
            del self.sequence[0]
            print(self.sequence)
            print(self.delay)
        else:
            self.delay = 0

        self.synci(400)  # give processor some time to configure pulses

    def body(self):
        '''
        Method that generates the assembly code that is looped over or repeated.
        For LaserOn this simply sets laser_gate_pmod to the high value
        '''

        # seq = []

        # for i in range(len(self.sequence)):
        #     seq.append(self.sequence[i][0])

        # time = self.delay
        # i = 0
        
        # while i < len(seq):
        #     self.trigger(pins=[self.cfg.laser_gate_pmod],
        #                  adc_trig_offset=0,
        #                  width=seq[i],
        #                  t=time)

        #     time += seq[i] + seq[i+1]
        #     i += 2

        # self.trigger(pins=[2,3],
        #              width=550,
        #              t=0)

        # self.trigger(pins=[0,2,3],
        #              width=500,
        #              t=499)

        pin1 = 0
        pin2 = 3
        out1 = 0
        out1 |= (1 << pin1)
        out2 = 0
        out2 |= (1 << pin1)
        out2 |= (1 << pin2)

        rp1 = 0
        r_out1 = 30


        rp2 = 0
        r_out2 = 31

        t_start1 = 0
        t_end1 = 500
        t_start2 = 500
        t_end2 = 1000

        trig_output = self.soccfg['tprocs'][0]['trig_output']

        print(self.soccfg['tprocs'][0])

        # Different registers

        # self.regwi(rp1, r_out1, out1)
        # self.seti(trig_output, rp1, r_out1, t_start1)
        # self.regwi(rp2, r_out2, out2)
        # self.seti(trig_output, rp2, r_out2, t_start2)
        # self.seti(trig_output, rp2, 0, t_end2)

        # Same register

        self.regwi(rp1, r_out1, out1)
        self.seti(trig_output, rp1, r_out1, t_start1)
        self.regwi(rp1, r_out1, out2)
        self.seti(trig_output, rp1, r_out1, t_start2)
        self.seti(trig_output, rp2, 0, t_end2)
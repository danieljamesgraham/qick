from qick import QickConfig
from qick import QickProgram

valid_channels = ["DAC_A", "DAC_B", "PMOD_0", "PMOD_1", "PMOD_2", "PMOD_3"]

class PickleParse():

    def __init__(self, imported_seqs, ch_map=None):
        self.pmod_sequence = [] # TODO: Remove!
        self.ch_cfg = {}

        # Allow sequences to be mapped to different channels
        if ch_map != None:
            self.pulse_seqs = {}
            for key, value in ch_map.items():
                self.pulse_seqs[key] = imported_seqs[value]
        else:
            self.pulse_seqs = imported_seqs

        # Check channel is valid
        for channel, seq_params in self.pulse_seqs.items():
            if channel not in valid_channels:
                raise Exception(channel, "Not a valid channel. Try any from:", 
                                valid_channels)
        
            # Extract channel information
            ch_type = channel.split('_')[0]
            ch_ref = channel.split('_')[1]
            
            # PMOD parsing -----------------------------------------------------
            if ch_type == "PMOD":
                print(f"----- PMOD {ch_ref} ------")
                time = 0
                lengths, times = [], []

                ch_index = ch_ref

                # Create lists of pulse parameters
                time = 0
                for l in seq_params:
                    if int(l[1]) == 1:
                        times.append(time/1e3) # Trigger time [us]
                        lengths.append(int(l[0])/1e3) # Pulse durations [us]
                    time += l[0]
                finish = time/1e3 # End time of sequence [us]


                # TODO: Move list creation outside of if condition



                # Convert list of tuples into list of lists
                seq_params = [list(t) for t in seq_params]

                # Convert pulse widths into elapsed time and append channel to 
                # list
                running_time = 0
                for l in seq_params:
                    l[0], running_time = running_time, running_time + l[0]
                    l.append(ch_index)
                
                delete_indices = []
                for i in range(len(seq_params) - 1):
                    if seq_params[i][1] == seq_params[i+1][1]:
                        delete_indices.append(i+1)
                for i in reversed(delete_indices):
                    del seq_params[i]
                
                # End final pulse
                seq_params.append([running_time, 0, ch_index])

                # Add channel sequence to master sequence and sort in order of 
                # time
                [self.pmod_sequence.append(l) for l in seq_params]
                self.pmod_sequence.sort(key=lambda x: x[0])

            # DAC parsing ------------------------------------------------------

            if ch_type == "DAC":
                print(f"----- DAC {ch_ref} -----")
                time = 0
                lengths, times, freqs = [], [], []

                # Assign correct QICK channel index
                if ch_ref == 'A':
                    ch_index = 1
                elif ch_ref == 'B':
                    ch_index = 0

                # Create lists of pulse parameters
                for l in seq_params:
                    if int(l[1]) == 1:
                        times.append(time/1e3) # Trigger time [us]
                        lengths.append(int(l[0])/1e3) # Pulse durations [us]
                        freqs.append(l[2]*1e3) # DAC frequency [Hz]
                    time += l[0]
                finish = time/1e3 # End time of sequence [us]

                # --------------------------------------------------------------

            # Raise error if pulse parameter lists are not equal in length
            num_pulses = len(lengths)
            if ((len(times) != num_pulses) or
                ((ch_type == "DAC") and (len(freqs) != num_pulses))):
                raise Exception("Number of elements in pulse parameter lists are not equal")

            # Create and print dictionary containing pulse parameters
            self.ch_cfg[channel] = {"ch_type": ch_type,
                                    "ch_index": ch_index,
                                    "num_pulses": num_pulses,
                                    "times": times,
                                    "lengths": lengths,
                                    "finish": finish
                                    }

            if ch_type == "DAC":
                self.ch_cfg[channel]["freqs"] = freqs

            for key, value in self.ch_cfg[channel].items():
                print(f"{key}: {value}")

        # Find and print time at which last state in sequence ends
        self.end_time = 0 
        for channel in self.ch_cfg:
            if self.ch_cfg[channel]["finish"] > self.end_time:
                self.end_time = self.ch_cfg[channel]["finish"]
        print(f"----- End time: {self.end_time} -----")


        # TODO: Raise error if end times don't match




    def dac_defaults(self, prog, gain, freq, phase):
        ch_cfg = self.ch_cfg

        for channel in ch_cfg:
            if ch_cfg[channel]["ch_type"] == "DAC":
                ch_index = ch_cfg[channel]["ch_index"]
                phase = prog.deg2reg(0, gen_ch=ch_index) # TODO: Set here and override later?
                gain = 10000 # TODO: Set here and override later?

                # Initialise DAC
                prog.declare_gen(ch=ch_index, nqz=1) 

                # Set default pulse parameters
                prog.default_pulse_registers(ch=ch_index, phase=phase, gain=gain) 

    def generate_asm(self, prog, reps=1):
        ch_cfg = self.ch_cfg
        soccfg = prog.soccfg
        pmod = soccfg['tprocs'][0]['output_pins'][0][1]

        # TODO: move outside and make DAC parameter
        offset = 38

        prog.synci(200)  # Give processor some time to configure pulses

        prog.regwi(0, 14, reps - 1) # 10 reps, stored in page 0, register 14
        prog.label("LOOP_I") # Start of internal loop

        for channel in ch_cfg:
            ch_index = ch_cfg[channel]["ch_index"]
            num_pulses = ch_cfg[channel]["num_pulses"]

            if ch_cfg[channel]["ch_type"] == "DAC":
                for i in range(num_pulses):
                    # TODO: Set phase and gain parameters
                    # phase = self.deg2reg(self.cfg["res_phase"], gen_ch=GEN_CH_A)
                    # gain = self.cfg["pulse_gain"]

                    # Pulse parameters
                    freq = prog.freq2reg(ch_cfg[channel]["freqs"][i], gen_ch=ch_index)
                    time = prog.us2cycles(ch_cfg[channel]["times"][i]) - offset
                    length = prog.us2cycles(ch_cfg[channel]["lengths"][i], gen_ch=ch_index)

                    # Store pulse parameters in register, then trigger pulse at given time
                    prog.set_pulse_registers(ch=ch_index, freq=freq, style="const", length=length)
                    prog.pulse(ch=ch_index, t=time)

            # if ch_cfg[channel]["ch_type"] == "PMOD":



            #     for i in range(num_pulses):
            #         time = prog.us2cycles(ch_cfg[channel]["times"][i])
            #         length = prog.us2cycles(ch_cfg[channel]["lengths"][i])





        out = 0
        for l in self.pmod_sequence:
            time = int(prog.us2cycles((l[0]) / 1e3))
            state = l[1]
            bit_position = int(l[2])

            if state == 1:
                out |= (1 << bit_position)
            elif state == 0:
                out &= ~(1 << bit_position)

            rp = 0 # tproc register page
            r_out = 31 # tproc register
            # print(bin(out), time)
            prog.regwi(rp, r_out, out)
            prog.seti(pmod, rp, r_out, time)
        print(len(self.pmod_sequence))

        prog.wait_all()
        prog.synci(prog.us2cycles(self.end_time))
        prog.loopnz(0, 14, "LOOP_I")
        prog.end()
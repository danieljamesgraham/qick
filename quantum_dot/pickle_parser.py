from qick import QickConfig
from qick import QickProgram

valid_channels = ["DAC_A", "DAC_B", "DIG_0", "DIG_1", "DIG_2", "DIG_3"]

class PickleParse():

    def __init__(self, imported_seqs, ch_map=None, delays={}):
        self.ch_cfg = {}
        self.dig_seq = {}

        # Allow sequences to be mapped to different channels
        if ch_map != None:
            self.pulse_seqs = {}
            for key, value in ch_map.items():
                self.pulse_seqs[key] = imported_seqs[value]
        else:
            self.pulse_seqs = imported_seqs

        # Check channel delay arguments are valid
        for channel, delay in delays.items():
            if channel not in valid_channels:
                raise Exception(f"{channel} is not a valid channel. Try any from:\n{valid_channels}")
            if type(delay) != int:
                raise Exception(f"{channel} delay ({delay}) must be an integer number of clock cycles")

        for channel, seq_params in self.pulse_seqs.items():
            lengths, times = [], []
            
            # Check channel names are valid
            # TODO: Times, states, frequencies and phases must be floats or ints
            if channel not in valid_channels:
                raise Exception(f"{channel} is not a valid channel. Try any from:\n{valid_channels}")

            # Extract channel information
            ch_type = channel.split('_')[0]
            ch_ref = channel.split('_')[1]
            
            if ch_type == "DIG":
                print(f"----- DIG {ch_ref} ------")
                ch_index = int(ch_ref)

            if ch_type == "DAC":
                print(f"----- DAC {ch_ref} -----")
                freqs, phases = [], []
                # Assign correct QICK channel index
                if ch_ref == 'A':
                    ch_index = 1
                elif ch_ref == 'B':
                    ch_index = 0

            if channel in delays: 
                delay = delays[channel] # Trigger delay [proc. clock cycles]
            else:
                delay = 0

            # Create lists of pulse parameters
            time = 0
            for l in seq_params:
                if bool(l[1]) == True:
                    times.append(time/1e3) # Trigger time [us]
                    lengths.append(l[0]/1e3) # Pulse durations [us]
                    if ch_type == "DAC":
                        freqs.append(l[2]*1e3) # DAC frequency [Hz]
                        phases.append(l[3]) # DAC phase [deg]
                time += l[0]
            finish = time/1e3 # End time of sequence [us]

            # Raise error if pulse parameter lists are not equal in length
            num_pulses = len(lengths)
            if ((len(times) != num_pulses) or
                ((ch_type == "DAC") and (len(freqs) != num_pulses))):
                raise Exception("Number of elements in pulse parameter lists are not equal")

            # Create and print dictionary containing pulse parameters
            self.ch_cfg[channel] = {"ch_type": ch_type,
                                    "ch_index": ch_index,
                                    "num_pulses": num_pulses,
                                    "delay": delay,
                                    "times": times,
                                    "lengths": lengths,
                                    "finish": finish,
                                    **({"freqs": freqs,
                                        "phases": phases}
                                       if ch_type == "DAC" else {})
                                    }
            for key, value in self.ch_cfg[channel].items():
                print(f"{key}: {value}")

        # Find and print time at which last state in sequence ends
        self.end_time = 0 
        for channel in self.ch_cfg:
            if self.ch_cfg[channel]["finish"] > self.end_time:
                self.end_time = self.ch_cfg[channel]["finish"]
        print(f"----- End time: {self.end_time} -----")


        # TODO: Raise error if end times don't match
        # TODO: Make sure not all parameters have to be specified for DAC
        # TODO: Make sure to raise error if too many parameters specified for DIG



    def dac_defaults(self, prog, gain, freq, phase):
        ch_cfg = self.ch_cfg

        # TODO: Default gain, frequency and phase if not specified?
        # Add gain for each pulse?
        # Add logic to maintain values if not specified for a pulse?

        for channel in ch_cfg:
            if ch_cfg[channel]["ch_type"] == "DAC":
                ch_index = ch_cfg[channel]["ch_index"]
                gain = 10000

                # Initialise DAC
                prog.declare_gen(ch=ch_index, nqz=1) 

                # Set default pulse parameters
                prog.default_pulse_registers(ch=ch_index, gain=gain) 

    def generate_asm(self, prog, reps=1):
        ch_cfg = self.ch_cfg
        soccfg = prog.soccfg
        dig_id = soccfg['tprocs'][0]['output_pins'][0][1]

        prog.synci(200)  # Give processor some time to configure pulses
        prog.regwi(0, 14, reps - 1) # 10 reps, stored in page 0, register 14
        prog.label("LOOP_I") # Start of internal loop

        for channel in ch_cfg:
            # Channel parameters
            ch_index = ch_cfg[channel]["ch_index"]
            num_pulses = ch_cfg[channel]["num_pulses"]
            delay = ch_cfg[channel]["delay"]

            if ch_cfg[channel]["ch_type"] == "DAC":
                for i in range(num_pulses):
                    # DAC pulse parameters
                    freq = prog.freq2reg(ch_cfg[channel]["freqs"][i], 
                                         gen_ch=ch_index)
                    phase = prog.deg2reg(ch_cfg[channel]["phases"][i],     
                                         gen_ch=ch_index)
                    time = prog.us2cycles(ch_cfg[channel]["times"][i]) + delay
                    length = prog.us2cycles(ch_cfg[channel]["lengths"][i], gen_ch=ch_index)

                    # Store DAC parameters in register and trigger pulse
                    prog.set_pulse_registers(ch=ch_index, freq=freq, phase=phase, 
                                             style="const", length=length)
                    prog.pulse(ch=ch_index, t=time)

            if ch_cfg[channel]["ch_type"] == "DIG":
                for i in range(num_pulses):
                    # DIG pulse parameters
                    time = prog.us2cycles(ch_cfg[channel]["times"][i]) + delay
                    length = prog.us2cycles(ch_cfg[channel]["lengths"][i])

                    # Add beginning of DIG pulse
                    if time in self.dig_seq:
                        self.dig_seq[time].append((ch_index, True))
                    else:
                        self.dig_seq[time] = [(ch_index, True)]

                    # Add end of DIG pulse
                    if time+length in self.dig_seq:
                        self.dig_seq[time+length].append((ch_index, False))
                    else:
                        self.dig_seq[time+length] = [(ch_index, False)]

                # Not strictly necessary but makes inspecting assembly easier
                self.dig_seq = dict(sorted(self.dig_seq.items()))

        # Program DIG after all channels have been configured
        r_val = 0
        rp, r_out = 0, 31 # tproc register page, tproc register
        for time, states in self.dig_seq.items():
            for l in states:
                ch_index = l[0]
                state = l[1]

                # Change DIG register to match desired state
                if state == True:
                    r_val |= (1 << ch_index)
                elif state == False:
                    r_val &= ~(1 << ch_index)

            # Write register values
            prog.regwi(rp, r_out, r_val)
            prog.seti(dig_id, rp, r_out, time)

        # Synchronise channels and loop
        prog.wait_all()
        prog.synci(prog.us2cycles(self.end_time))
        prog.loopnz(0, 14, "LOOP_I")
        prog.end()
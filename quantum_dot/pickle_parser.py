from qick import QickConfig
from qick import QickProgram

valid_channels = ["DAC_A", "DAC_B", "DIG_0", "DIG_1", "DIG_2", "DIG_3"]

# TODO: Default constants
DEFAULT_DELAY = 0
DEFAULT_GAIN = 10000

class PickleParse():

    def __init__(self, imported_seqs, ch_map=None, gains={}, delays={}):
        self.ch_cfg = {}
        self.dig_seq = {}

        # Allow sequences to be mapped to different channels
        if ch_map != None:
            self.pulse_seqs = {}
            for key, value in ch_map.items():
                self.pulse_seqs[key] = imported_seqs[value]
        else:
            self.pulse_seqs = imported_seqs

        # TODO: Move checks into separate function
        self.check_delays(delays)
        # Check channel delay arguments are valid


        # TODO: Gain and amplitude parameter checks (ie. int between 1 and 30000)
        self.check_amplitudes(gains)

        for channel, seq_params in self.pulse_seqs.items():
            lengths, times = [], []
            
            # Check channel names are valid
            # TODO: Times, amps, frequencies and phases must be floats or ints
            # Max freq = 10GHz
            # Max amp=1
            # TODO: Specify minimum pulse durations
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
                amps, freqs, phases = [], [], []
                # Assign correct QICK channel index
                if ch_ref == 'A':
                    ch_index = 1
                elif ch_ref == 'B':
                    ch_index = 0

            if channel in delays: 
                delay = delays[channel] # Trigger delay [proc. clock cycles]
            else:
                delay = DEFAULT_DELAY
            
            if channel in gains:
                gain = gains[channel]
            else:
                gain = DEFAULT_GAIN

            # Create lists of pulse parameters
            time = 0
            for l in seq_params:
                # Add pulse parameters to respective lists
                if (bool(l[1]) == False) and (len(l) > 2):
                    raise Exception(f"Specified too many sequence parameters for pulse in channel {channel}")
                elif bool(l[1]) == True:
                    if ((len(l) > 2) and (ch_type == "DIG")
                        or (len(l) > 4) and (ch_type == "DAC")):
                        raise Exception(f"Specified too many sequence parameters for pulse in channel {channel}")

                    times.append(time/1e3) # Trigger time [us]
                    lengths.append(l[0]/1e3) # Pulse durations [us]

                    if ch_type == "DAC":
                        amps.append(l[1])
                        freqs.append(l[2]*1e3) # DAC frequency [Hz]
                        phases.append(l[3]) # DAC phase [deg]

                time += l[0]
            duration = time/1e3 # End time of sequence [us]

            # Raise error if pulse parameter lists are not equal in length
            num_pulses = len(lengths)
            if ((len(times) != num_pulses) or
                ((ch_type == "DAC") and (len(freqs) != num_pulses))):
                raise Exception("Number of elements in pulse parameter lists are not equal")

            # Create and print dictionary containing pulse parameters
            self.ch_cfg[channel] = {"ch_type": ch_type,
                                    "ch_index": ch_index,
                                    "num_pulses": num_pulses,
                                    "duration": duration,
                                    "delay": delay,
                                    "gain": gain,
                                    "times": times,
                                    "lengths": lengths,
                                    **({"amps": amps,
                                        "freqs": freqs,
                                        "phases": phases}
                                       if ch_type == "DAC" else {})
                                    }
            for key, value in self.ch_cfg[channel].items():
                print(f"{key}: {value}")

        # Find and print time at which longest sequence ends
        end_times = [self.ch_cfg[channel]["duration"] for channel in self.ch_cfg]
        self.end_time = max(end_times)

        print(f"----- End time: {self.end_time} -----")
        if not all(i == end_times[0] for i in end_times):
            print("WARNING! Not all sequences are of the same duration")

        # TODO: Make sure not all parameters have to be specified for DAC
        # FIXME: Make sure to raise error if too many parameters specified for DIG
        # TODO: Add check for DAC gain

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
                prog.declare_gen(ch=ch_index, nqz=1) 

                for i in range(num_pulses):
                    # DAC pulse parameters
                    time = prog.us2cycles(ch_cfg[channel]["times"][i]) + delay
                    length = prog.us2cycles(ch_cfg[channel]["lengths"][i], gen_ch=ch_index)
                    amp = int(ch_cfg[channel]["amps"][i] * ch_cfg[channel]["gain"])
                    freq = prog.freq2reg(ch_cfg[channel]["freqs"][i], 
                                         gen_ch=ch_index
                                         )
                    phase = prog.deg2reg(ch_cfg[channel]["phases"][i],     
                                         gen_ch=ch_index
                                         )

                    # Store DAC parameters in register and trigger pulse
                    prog.set_pulse_registers(ch=ch_index,
                                             gain=amp,
                                             freq=freq, 
                                             phase=phase,
                                             style="const",
                                             length=length
                                             )
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

    def check_channel(self, channel):
        if channel not in valid_channels:
            raise Exception(f"{channel} is not a valid channel. Try any from:\n{valid_channels}")
    
    def check_amplitudes(self, gains):
        for channel, gain in gains.items():
            self.check_channel(channel)
            if not isinstance(gain, (int, float)):
                raise Exception(f"{channel} gain '{gain}' must be an int or a float")
            if abs(gain) > 30000:
                raise Exception(f"{channel} gain magnitude '{gain}' must not be greater than 30000")

    def check_delays(self, delays):
        for channel, delay in delays.items():
            self.check_channel(channel)
            if type(delay) != int:
                raise Exception(f"{channel} delay ({delay}) must be an integer number of clock cycles")
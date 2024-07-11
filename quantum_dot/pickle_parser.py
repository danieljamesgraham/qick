# TODO: Extract parsing function and inherit it instead.

from qick import QickConfig
from qick import QickProgram

class PickleParse():
    sequence = []

    def __init__(self, imported_seqs, ch_map=None):
        self.ch_cfg = {}

        if ch_map != None:
            self.pulse_seqs = {}
            for key, value in ch_map.items():
                self.pulse_seqs[key] = imported_seqs[value]
        else:
            self.pulse_seqs = imported_seqs


        valid_channels = ["DAC_A", "DAC_B", "PMOD_0", "PMOD_1", "PMOD_2", "PMOD_3"]

        for channel, seq_params in self.pulse_seqs.items():

            # Check validity of arguments and extract channel info -------------

            if channel not in valid_channels:
                raise Exception(channel, "Not a valid channel. Try any from:", 
                                valid_channels)
        
            ch_type = channel.split('_')[0]
            ch_index = channel.split('_')[1]
            
            # PMOD parsing -----------------------------------------------------

            if ch_type == "PMOD":
                print("----- PMOD ------")

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
                [self.sequence.append(l) for l in seq_params]
                self.sequence.sort(key=lambda x: x[0])

            # DAC parsing ------------------------------------------------------

            if ch_type == "DAC":
                print("----- DAC -----")

                pulse_lens = []
                on_times = []
                on_freqs = []

                if ch_index == 'A':
                    ch_ref = 1
                elif ch_index == 'B':
                    ch_ref = 0

                for l in seq_params:
                    if int(l[1]) == 1:
                        pulse_lens.append(int(l[0])/1e3)

                running_time = 0
                for l in seq_params:
                    if int(l[1]) == 1:
                        on_times.append(running_time/1e3)
                        on_freqs.append(l[2]*1e3)
                    running_time += l[0]
                finish_time = running_time/1e3

                if len(pulse_lens) != len(on_times):
                    raise ValueError # TODO: Make error less generic
                
                seq_length = len(pulse_lens)
                # TODO: Actually implement this
                # TODO: Class-wide variable that stores sequence lengths

                # print(pulse_lens, on_times, on_freqs, finish_time)
                self.ch_cfg[channel] = {"pulse_lens": pulse_lens,
                                        "times": on_times,
                                        "freqs": on_freqs,
                                        "finish": finish_time,
                                        "num_pulses": seq_length,
                                        "ch_type": ch_type,
                                        "ch_ref": ch_ref
                                        }
                
                for key, value in self.ch_cfg[channel].items():
                    print(key, value)

        # Post-parsing information ---------------------------------------------

        last_finish = 0 
        for channel in self.ch_cfg:
            if self.ch_cfg[channel]["finish"] > last_finish:
                last_finish = self.ch_cfg[channel]["finish"]
        print("Last finish:", last_finish)

# ------------------------------------------------------------------------------

    def dac_defaults(self, prog, gain, freq, phase):
        # TODO: Make generic
        prog.declare_gen(ch=1, nqz=1) # Initialise DAC
        phase = prog.deg2reg(0, gen_ch=1) # TODO: Set here and override later?
        gain = 10000 # TODO: Set here and override later?
        prog.default_pulse_registers(ch=1, phase=phase, gain=gain) # Set default pulse parameters

    def generate_asm(self, prog, reps=1):
        ch_cfg = self.ch_cfg
        soccfg = prog.soccfg
        pmod = soccfg['tprocs'][0]['output_pins'][0][1]

        # TODO: move outside
        offset = 38

        prog.synci(200)  # Give processor some time to configure pulses

        prog.regwi(0, 14, reps - 1) # 10 reps, stored in page 0, register 14
        prog.label("LOOP_I") # Start of internal loop

        # Configure DAC pulses
        # TODO: tidy by taking objects out of functions

        for channel in ch_cfg:
            ch_ref = ch_cfg[channel]["ch_ref"]
            num_pulses = ch_cfg[channel]["num_pulses"]

            if ch_cfg[channel]["ch_type"] == "DAC":
                for i in range(num_pulses):
                    # TODO: Set phase and gain parameters
                    # phase = self.deg2reg(self.cfg["res_phase"], gen_ch=GEN_CH_A)
                    # gain = self.cfg["pulse_gain"]

                    # Pulse parameters
                    freq = prog.freq2reg(ch_cfg["DAC_A"]["freqs"][i], gen_ch=ch_ref)
                    time = prog.us2cycles(ch_cfg["DAC_A"]["times"][i]) - offset
                    pulse_len = prog.us2cycles(ch_cfg["DAC_A"]["pulse_lens"][i], gen_ch=ch_ref)

                    # Store pulse parameters in register, then trigger pulse at given time
                    prog.set_pulse_registers(ch=ch_ref, freq=freq, style="const", length=pulse_len)
                    prog.pulse(ch=ch_ref, t=time)
        
        out = 0
        for l in PickleParse.sequence: 
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

        prog.wait_all()
        prog.synci(prog.us2cycles(ch_cfg["DAC_A"]["finish"]))
        prog.loopnz(0, 14, "LOOP_I")
        prog.end()
# TODO: Extract parsing function and inherit it instead.

from qick import QickConfig

class PickleParse():
    sequence = []

    def __init__(self, pulse_sequences):
        # self.soccfg = soccfg
        self.pulse_sequences = pulse_sequences
        self.ch_cfg = {}

        valid_channels = ["DAC_A", "DAC_B", "PMOD_0", "PMOD_1", "PMOD_2", "PMOD_3"]

        for channel, seq_params in self.pulse_sequences.items():

            # Check validity of arguments and extract channel info -------------

            if channel not in valid_channels:
                raise Exception(channel, "is not a valid output")
        
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

    def configure(self, soccfg):
        self.soccfg = soccfg
        
        out = 0
        for l in DigitalOutput.sequence: 
            time = int(QickConfig.us2cycles((l[0]) / 1e3))
            state = l[1]
            bit_position = l[2]

            if state == 1:
                out |= (1 << bit_position)
            elif state == 0:
                out &= ~(1 << bit_position)

            rp = 0 # tproc register page
            r_out = 31 # tproc register
            # print(bin(out), time)
            self.regwi(rp, r_out, out)
            self.seti(soccfg['tprocs'][0]['output_pins'][0][1], rp, r_out, time)




class DigitalOutput():
    sequence = []

    def __init__(self, soccfg, pmod_ch, seq):
        self.soccfg = soccfg
        self.pmod_ch = pmod_ch
        self.seq = seq

        # Remove pre-exisiting sequence if it already exists for channel
        for l in self.sequence[:]:
            if l[-1] == self.pmod_ch:
                self.sequence.remove(l)
        
        if self.seq != None:
            # Convert list of tuples into list of lists
            self.seq = [list(t) for t in self.seq]

            # Convert pulse widths into elapsed time and append channel to list
            time = 0
            for l in self.seq:
                l[0], time = time, time + l[0]
                l.append(pmod_ch)

            delete_indices = []
            for i in range(len(self.seq) - 1):
                if self.seq[i][1] == self.seq[i+1][1]:
                    delete_indices.append(i+1)
            for i in reversed(delete_indices):
                del self.seq[i]
            
            # End final pulse
            self.seq.append([time, 0, pmod_ch])

            # Add channel sequence to master sequence and sort in order of time
            [self.sequence.append(l) for l in self.seq]
            self.sequence.sort(key=lambda x: x[0])
        
    def configure(self, soccfg):
        self.soccfg = soccfg
        
        out = 0
        for l in DigitalOutput.sequence: 
            time = int(self.us2cycles((l[0]) / 1e3))
            state = l[1]
            bit_position = l[2]

            if state == 1:
                out |= (1 << bit_position)
            elif state == 0:
                out &= ~(1 << bit_position)

            rp = 0 # tproc register page
            r_out = 31 # tproc register
            # print(bin(out), time)
            self.regwi(rp, r_out, out)
            self.seti(soccfg['tprocs'][0]['output_pins'][0][1], rp, r_out, time)
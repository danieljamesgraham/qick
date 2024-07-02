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

seq_0 = DigitalOutput(0, [(10e3, 1), (15e3, 0), (25e3, 1)])
seq_1 = DigitalOutput(1, [(15e3, 1), (10e3, 0), (15e3, 1)])
print(DigitalOutput.sequence)

# TODO - Account for identical times?

out = 0
# trig_output = self.soccfg['tprocs'][0]['trig_output']

for l in DigitalOutput.sequence: 
    time = l[0]
    state = l[1]
    bit_position = l[2]

    if state == 1:
        out |= (1 << bit_position)
    elif state == 0:
        out &= ~(1 << bit_position)

    print(bin(out), time)
    # self.regwi(0, 31, out)
    # self.seti(trig_output, 0, time)
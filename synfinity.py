#py 3.13
from tkinter.ttk import Combobox
import numpy as np

import soundfile as sf
import sounddevice as sd

from tkinter import *
from tkdial import Dial
from tkinter import filedialog

import threading as tr

samplerate=44100
print("online")

root=Tk()
root.title("infinite synth")
root.geometry("700x500")
root.configure(bg="gray")

#scrollable frame class from https://blog.teclado.com/tkinter-scrollable-frames/
#place things inside self.scrollable_frame

class ScrollBox(Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = Canvas(self)
        scrollbar = Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

#list containing controls for each osc. each item is its own list of (row,label,freq,mag,toggle,remove)
osccontrols={}
maxid=0
def add_wave(freq=0, mag=0, phase=0):
    global maxid
    id=maxid
    #add a wave with next numerical id, default 440hz
    wave_list[id]=CosWave(freq, mag, phase)
    #add gui controls for the wave
    osccontrols[id]=[0,1,2,3,4,5,6,Combobox(),8]

    #container for 1 row of controls for 1 osc
    row=Frame(scrollbox.scrollable_frame)
    osccontrols[id][0]=row
    osccontrols[id][0].pack(side="top")

    label=Label(row, text=("Osc",id))
    osccontrols[id][1]=label
    osccontrols[id][1].pack(side="left")

    #controls the frequency
    freqdial=Dial(row, start=0, end=1000, text="freq: ", width=50,radius=15, unit_length=3, unit_width=1, 
                  command=lambda:setattr(wave_list[id], "frequency", osccontrols[id][2].get()))
    #freqdial.set(freq)
    osccontrols[id][2]=freqdial
    osccontrols[id][2].pack(side="left")

    #controls the magnitude
    magdial=Dial(row, start=0, end=1, text="mag: ",width=50, radius=15, unit_length=3, unit_width=1,
                 command=lambda:makethecheckboxfrickinwork())
    #magdial.set(mag)
    osccontrols[id][3]=magdial
    osccontrols[id][3].pack(side="left")

    #controls the phase
    phasedial=Dial(row, start=0, end=2*np.pi, text="phase: ", width=50,radius=15, unit_length=3, unit_width=1, 
                  command=lambda:setattr(wave_list[id], "phase", osccontrols[id][4].get()))
    #phasedial.set(phase)
    osccontrols[id][4]=phasedial
    osccontrols[id][4].pack(side="left")

    #toggle the oscillator on or off by setting the magnitude to 0 if off
    tk_magnitude=IntVar(value=1)
    toggle=Checkbutton(row, text="on/off", variable=tk_magnitude, offvalue=0, onvalue=1, command=lambda:makethecheckboxfrickinwork())
    osccontrols[id][5]=toggle
    osccontrols[id][5].pack(side="left")

    def makethecheckboxfrickinwork():
        if tk_magnitude.get()==1:
            wave_list[id].amplitude=osccontrols[id][3].get()
            print("osc",wave_list[id],"on")
        else:
            wave_list[id].amplitude=0
            print("osc",wave_list[id],"off")

    #remove the osc
    removebtn=Button(row, text="remove osc", command=lambda:remove_wave(id))
    osccontrols[id][6]=removebtn
    osccontrols[id][6].pack(side="left")
    
    #route the osc to become a controller
    #dropdown to select oscillator
    oscselect=Combobox(row, state="readonly", values=["osc"]+list(wave_list.keys()))
    oscselect.current(0)
    oscselect.bind("<<ComboboxSelected>>", lambda e :automation_selected(id))
    osccontrols[id][7]=oscselect
    osccontrols[id][7].pack(side="left")
    #update all the other dropdowns with the new oscillator
    for ctrl in osccontrols.keys():
        osccontrols[ctrl][7].configure(values=["osc"]+list(wave_list.keys()))

    #dropdown to select which control is being automated
    ctrlselect=Combobox(row, state="readonly", values=["Control","freq", "mag"])
    ctrlselect.current(0)
    osccontrols[id][8]=ctrlselect
    osccontrols[id][8].pack(side="left")
    print("added osc")

    maxid+=1

#dictionary with automated wave id: control wave
automated_waves={}
def automation_selected(id):
    control=osccontrols[id][7].get()
    if not control=="osc":
        automated_waves[int(control)]=[wave_list[id],id]
        print("added automation")
        print(automated_waves)

    else:
        print("finding automation to remove")
        for key in automated_waves.keys():
            if automated_waves[key]==[wave_list[id],id]:
                automated_waves.pop(key, None)
                print("removed automation")
                print(automated_waves)
                break
        

def remove_wave(id):
    for i in range(6):
        osccontrols[id][0].destroy()
    wave_list.pop(id)



#Generate a cosine wave
'''class CosWave:
    def __init__(self, frequency, amplitude, phase=0):
        self.frequency = frequency
        self.amplitude = amplitude
        
        self.phase = phase

    def generate_block(self, frames, samplerate ):
        #Calculate phase increment for every time step
        phase_step = 2 * np.pi * self.frequency / samplerate
        
        #Generate a list of every phase in this block for the buffer
        phases = self.phase + np.arange(frames) * phase_step
        
        #Step to the phase for the next block
        self.phase += frames * phase_step
        # Keep the phase bounded to avoid precision loss over time
        self.phase %= 2 * np.pi
        
        return self.amplitude * np.cos(phases)'''


wave_list = {} #list of CosWave objects containing freq, mag, phase

#improved to allow frequency modulation
class CosWave:
    def __init__(self, frequency, amplitude, phase=0):
        self.frequency = frequency
        self.amplitude = amplitude
        self.phase = phase

    def generate_block(self, frames, samplerate, modulator=None, deviation=0):
        # Calculate instantaneous frequency for each sample
        if modulator is None:
            phase_step = 2 * np.pi * self.frequency / samplerate
            phase_steps = np.full(frames, phase_step)
        else:
            frequencies = self.frequency + deviation * modulator
            phase_steps = 2 * np.pi * frequencies / samplerate

        # Accumulate phase increments across this block
        phases = self.phase + np.concatenate(([0.0], np.cumsum(phase_steps[:-1])))

        # Update phase for the next block
        self.phase = (self.phase + np.sum(phase_steps)) % (2 * np.pi)

        return self.amplitude * np.cos(phases)

def start_wave(voice, freq, mag, phase=0):
    wave_list[voice]=CosWave(freq, mag, phase)
    print("started voice",voice,"freq",freq,"mag",mag)
    print(wave_list)

def stop_wave(voice):   
    wave_list[voice].pop()

def audio_callback(outdata, frames, time, status):

    # Start with a silent block of zeros
    mixed_buffer = np.zeros(frames)
    
    # Mathematically add each wave's array into the master buffer.
    #the frames are every sample step for that block
                   

    for wave_id, wave in wave_list.items():
        
        route=osccontrols[wave_id][7].get()
        if route=="osc":
            if wave_id in automated_waves.keys():
                controllerwavectrls=automated_waves[wave_id][1]
                if osccontrols[controllerwavectrls][8].get()=="mag":
                    target=wave.generate_block(frames, samplerate)
                    effect=automated_waves[wave_id][0].generate_block(frames, samplerate)
                    result = np.multiply(target, (effect+1)*0.5)
                    mixed_buffer+=result
                                        
                elif osccontrols[controllerwavectrls][8].get()=="freq":
                    effect=automated_waves[wave_id][0].generate_block(frames, samplerate)
                    result=wave.generate_block(frames, samplerate, modulator=effect, deviation=100)
                    mixed_buffer+=result

            else:
                mixed_buffer += wave.generate_block(frames, samplerate)



    # Write the mixed mono signal into the stream's output channel(s)
    outdata[:, 0] = mixed_buffer

#Initialize the stream without starting it immediately
stream = sd.OutputStream(
    channels=1,
    callback=audio_callback,
    samplerate=samplerate,
    dtype='float32'
)


##### import wave data


def import_data():
    file=filedialog.askopenfilename(title="Import Data", filetypes=[("Numpy Archive", "*.npz")])
    if file:
        data=np.load(file)
        frequencies = data["frequencies"]
        magnitudes = data["magnitudes"]
        angles = data["angles"]
        for i in range(len(frequencies)):
            add_wave(frequencies[i], magnitudes[i], angles[i])

importthread=tr.Thread(target=import_data)
            

###other gui elements
startsound = Button(root,text="start sound",command=lambda:stream.start())
stopsound = Button(root, text="stop sound", command=lambda:stream.stop())

startsound.pack()
stopsound.pack()

addwave = Button(root, text="add osc", command=add_wave)
addwave.pack()

importbtn= Button(root, text="import data", command=lambda: importthread.start())
importbtn.pack()

scrollbox=ScrollBox(root)
scrollbox.pack(fill="both", expand=True)

root.mainloop()
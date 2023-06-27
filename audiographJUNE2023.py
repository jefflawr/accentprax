import wave
import pyaudio
import struct
import numpy as np
import time
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg)
from matplotlib.figure import Figure
from accentaudiocontrolsMin import *
# from thread_with_trace import *
import threading
import tkinter as tk
from database import AccentDatabase
import queue
import librosa


class AudioGraph:
    """Class to play and graph audio file
    Attributes:
        frame:              whole frame to hold graph and audio controls
        controls:           AccentAudioControls for audio playback & recording
        canvas:             tkinter Canvas to graph amplitude sonograph
        spect_fig:          tkinter Figure to hold spect_canvas
        spect_canvas:       FigureCanvasTkAgg canvas to graph spectrogram and intensity
        audio_file:         audio file to record, play and graph
        model_file:         current filename without path
        model_filepath:     complete path to current audio file
        student_file:       current filename without path
        student_filepath:   complete path to current audio file
        audio_stream:       pyaudio audio stream for recording and playback
        student_recording:         boolean that determines presence/absence of "record" button on controls
        py_object:          pyAudio object to manage playback
        play_thread:        play thread
        record_thread:      record thread


    Methods:
        __init__(self, mainWindow, UI_frame, record=False, model_audiograph)
        get_model_phrase()
        select_audio_file()
        reset_labels()
        draw_axes()
        reset_graph()
        update_playback_speed()
        draw_spectrogram()
        draw_intensity()
        plot_amp_chunk()
        poll_queue()
        play_file()
        stop_playrecord_thread()
        start_play_thread()
        record_file()
        draw_axes()
        play_file()
        plot_spectgram()
    """
    # Audiograph class attributes
    frame, controls, canvas, marker_line_id, shift = None, None, None, None, None
    spect_fig, spect_canvas, spect_axes = None, None, None
    file_select_button, filename_text, = None, None
    model_file, model_filepath, student_file = None, None, None
    audio_stream, audio_file, audio_data, py_object = None, None, None, None
    play_thread, record_thread = None, None
    student_recording, playing, recording = False, False, False
    student_filepath = "student_file.wav"
    DEFAULT_CLIP_LENGTH = 3
    DEFAULT_FRAMERATE = 22050
    RECORD_CHUNK = 8000
    CHUNK = 256
    bin_chunk_ratio = .25
    LABEL_WIDTH = 50
    LABEL_HEIGHT = 50
    CANVAS_WIDTH = 800
    CANVAS_HEIGHT = 150
    PLAY_BACK_SPEED = 1

    # args: root=mainWindow, UI_frame=mainWindow's frame, record_flag=True/False, model_audiograph)

    def __init__(self, root, UI_frame, record_flag, model_audiograph):
        self.QUEUE = queue.Queue()
        self.POLLING_INTERVAL = 500
        self.model_min_y = None
        self.model_max_y = None
        self.graph_data = None
        self.root = root
        self.student_recording = record_flag
        self.frame = UI_frame
        self.canvas_width = self.CANVAS_WIDTH
        self.canvas_height = self.CANVAS_HEIGHT
        self.record_object = None
        self.chunk = self.CHUNK
        self.fs = None
        self.duration = None

        self.playback_speed = self.PLAY_BACK_SPEED
        self.info_panel = tk.Frame(self.frame, background="light gray")
        self.info_panel.grid(row=0,column=0, rowspan=6)

        # set up canvas to plot amplitude waveform
        self.amp_graph_canvas = tk.Canvas(self.frame, background="white", width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT)
        self.draw_axes()
        self.nothing_recorded = True
        self.amp_graph_canvas.grid(row=1, column=1, rowspan=4, columnspan=6)
        self.spect_fig = Figure(figsize=(8.05, 1.56), dpi=100)
        self.spect_fig.subplots_adjust(left=0, right=1, bottom=0, top=1, wspace=0, hspace=0)
        self.spect_canvas = FigureCanvasTkAgg(self.spect_fig, master=self.frame)  # A tk.DrawingArea.
        self.spect_canvas.get_tk_widget().grid(row=5, column=1, rowspan=4, columnspan=6)
        self.sp_axes = self.spect_fig.add_subplot()       # sp_axes is for spectrogram plot
        self.sp_axes.axis("off")                             # turn off axis labels for spectrogram plot

        # set up controls - self.student_recording determines whether Record button appears
        if self.student_recording == False:
            self.control_frame = tk.Frame(self.frame, background="light gray")
            filler_frame = tk.Frame(self.frame, background="light gray")
            filler_frame.grid(row=10, column=1, sticky="w")
            self.control_frame.grid(row=10, column=2, sticky="w")
            self.controls = AccentAudioControls(self.control_frame, self.student_recording)
            # self.controls.stop_button.configure(command=lambda: self.stop_playrecord_thread(self.model_filepath))
            self.controls.play_button.configure(command=lambda: self.start_play_thread(self.model_filepath))
        else:
            self.control_frame = tk.Frame(self.frame, background="light gray")
            self.control_frame.grid(row=10, column=2, sticky="nsew")
            self.controls = AccentAudioControls(self.control_frame, self.student_recording)
            # self.controls.stop_button.configure(command=lambda: self.stop_playrecord_thread(self.student_filepath))
            self.controls.play_button.configure(command=lambda: self.start_play_thread(self.student_filepath))

        # set up frames to display info about the practice text
        self.phrase_text_frame = tk.Frame(self.frame,background="light gray")
        self.phrase_text_frame.grid(row=9, column=1, sticky="n", columnspan=6)
        self.phrase_text = tk.StringVar()
        self.phrase_text_label = tk.Label(self.phrase_text_frame, textvariable=self.phrase_text, background="light gray")
        self.phrase_text_label.grid(row=0, column=0)

        # other setup, depending on whether recording is enabled (i.e. if it's a student display)
        if self.student_recording is True:             # if student frame, set up scratch file
            tk.Label(self.info_panel, text="Student Speaker", background="light gray").grid(row=0, column=0, sticky="nsew")
            tk.Label(self.info_panel, text="", background="light gray").grid(row=1, column=0, sticky="nsew")

            # instantiate and initialize record button
            self.controls.record_button.configure(command=lambda: self.start_record_thread(self.student_filepath))
            score_frame = tk.LabelFrame(self.info_panel, height=self.LABEL_HEIGHT * 5, width=self.LABEL_WIDTH,
                                        background="light gray", borderwidth=0, highlightthickness=0,
                                        text="Scoreboard          ")
            # set up scoring widgets
            score_frame.grid(row=2, column=0, sticky='ns')
            difficulty_frame = tk.LabelFrame(score_frame, width=self.LABEL_WIDTH, height=self.LABEL_HEIGHT,
                                             borderwidth=0, highlightthickness=0, background="light gray",
                                             text="Difficulty Level")
            difficulty_frame.grid(row=0, column=0, sticky='nsew')
            difficulty_slider = tk.Scale(difficulty_frame, sliderlength=10, width=10, from_=10, to=100,
                                         resolution=10, background="light gray", orient="horizontal")
            difficulty_slider.set(100)
            difficulty_slider.grid(row=0, column=0, sticky="ew")
            student_last = tk.LabelFrame(score_frame, width=100, height=50, background="light gray",
                                         borderwidth=0, highlightthickness=0, text="Last Try")
            student_last.grid(row=2, column=0, sticky='nsew')
            last_score = tk.Label(student_last, text="  %", background="white")
            last_score.grid(row=0, column=0)
            student_avg = tk.LabelFrame(score_frame, width=100, height=50, background="light gray",
                                        borderwidth=0, highlightthickness=0, text="Average")
            student_avg.grid(row=3, column=0, sticky='nsew')
            avg_score = tk.Label(student_avg, text="  %", background="white")
            avg_score.grid(row=0, column=0)
            avg_reset_frame = tk.LabelFrame(score_frame, width=self.LABEL_WIDTH, height=self.LABEL_HEIGHT,
                                            borderwidth=0, highlightthickness=0, background="light gray",
                                            text="Reset Scores")
            avg_reset_frame.grid(row=4, column=0, sticky='nsew')
            reset_button = tk.Button(avg_reset_frame, background="light gray", relief="sunken", text="Reset")
            reset_button.grid(row=5, column=0, sticky='nsew')

        # Model speaker setup - no record button or scoring
        else:
            self.model_filepath = None
            tk.Label(self.frame, text="Model Speaker    ",
                     background="light gray").grid(row=2, column=0, sticky="nsew")
            # pop-up audio file selector button
            self.file_select_button = tk.Button(self.frame, background="light gray",
                                                command=lambda: self.select_audio_file(),
                                                text="Select Model File")
            self.file_select_button.grid(row=0, column=1)
            self.filename_text = tk.StringVar()
            self.filename_text.set("Nothing Selected")
            filename_frame = tk.LabelFrame(self.frame, text="Model File", background="light gray",
                                           borderwidth=0, highlightthickness=0)
            filename_frame.grid(row=0, column=2)
            name_label = tk.Label(filename_frame,
                                  textvariable=self.filename_text, background="light gray")
            name_label.grid(row=0, column=0)

            self.language_text = tk.StringVar()
            self.language_text.set("<none chosen>")
            language_label_frame = tk.LabelFrame(self.frame, text="Language", background="light gray",
                                                 borderwidth=0, highlightthickness=0)
            language_label_frame.grid(row=0, column=3)
            language_label = tk.Label(language_label_frame,
                                      textvariable=self.language_text, background="light gray")
            self.notes_text = tk.StringVar()
            self.notes_text.set("<none chosen>")
            notes_label_frame = tk.LabelFrame(self.frame, text="Problematic Sounds", background="light gray",
                                              borderwidth=0, highlightthickness=0)
            notes_label_frame.grid(row=0, column=4)
            language_label = tk.Label(notes_label_frame, textvariable=self.notes_text, background="light gray")
            language_label.grid(row=0, column=0)

        # set up audio playback speed control -
        speed_frame = tk.LabelFrame(self.frame, text="Playback Speed", width=250, background="light gray")
        speed_frame.grid(row=10, column=1, sticky="w")
        self.speed_scale = tk.Scale(speed_frame, sliderlength=10, width=25, from_=25, to=100,
                                    command=self.update_playback_speed,
                                    resolution=25, background="light gray", orient="horizontal")
        self.speed_scale.set(100)
        self.speed_scale.grid(row=0, column=0)

    def model_file_info(self):
        duration = self.duration
        return duration

    def get_model_phrase_text(self):
        return(self.phrase_text.get())

    def select_audio_file(self):      # called by file selector button to choose audio file
        modal = tk.Toplevel()
        modal.geometry("400x200")

        def onselect(evt):
            w = evt.widget
            index = int(w.curselection()[0])
            modal.destroy()

            # stop current activity
            self.stop_playrecord_thread(self.model_filepath)
            self.model_filepath = "menufiles/" + AccentDatabase[index]['file']
            self.model_file = AccentDatabase[index]['file']
            self.language_text.set(AccentDatabase[index]['lang'])
            self.notes_text.set(AccentDatabase[index]['notes'])
            self.audio_file = wave.open(self.model_filepath, 'rb')
            # self.phrase_text.set(AccentDatabase[index]['lang'])
            self.filename_text.set(AccentDatabase[index]['file'])
            self.reset_labels()

        Lb = tk.Listbox(modal, width=400, height=200)
        scrollbar = tk.Scrollbar(modal)
        scrollbar.pack(side="right", fill="both")
        Lb.config(yscrollcommand = scrollbar.set)
        scrollbar.config(command = Lb.yview)

        for i, d in enumerate(AccentDatabase):
            Lb.insert(i+1, '{}'.format(d['name']))
        Lb.bind('<<ListboxSelect>>', onselect)
        Lb.pack()
        modal.mainloop()

    def reset_labels(self):  # open file for recording, playing, graphing
        if self.model_filepath == "":
            return
        else:
            self.model_file=(self.model_filepath.split('/')[-1])
            # self.filename_text.set(self.model_file)
            self.reset_graph()

    def draw_axes(self):        # sets up tick marks on amp_graph_canvas for amplitude graph
        SHORT_TICK = 10
        TALL_TICK = 100
        GRAPH_TICKS = 300

        graph_tick_number = GRAPH_TICKS
        x_origin = 0
        y_zero = self.amp_graph_canvas.winfo_height() / 2
        tick_distance = self.amp_graph_canvas.winfo_width() / graph_tick_number
        for tick_no in range(x_origin, graph_tick_number + 1):
            tick_x = x_origin + tick_no * tick_distance
            if tick_no % 20 == 0:
                self.amp_graph_canvas.create_line(tick_x, y_zero + TALL_TICK,
                                                  tick_x, y_zero - TALL_TICK,
                                                  fill="light gray")
            elif tick_no % 2 == 0:
                self.amp_graph_canvas.create_line(tick_no * tick_distance, y_zero + SHORT_TICK,
                                                  tick_no * tick_distance, y_zero - SHORT_TICK,
                                                  fill="light gray")

    def reset_graph(self):      # resets amp_graph_canvas for a new graph
        self.amp_graph_canvas.delete('all')
        self.draw_axes()
        self.spect_fig = Figure(figsize=(8.05, 1.56), dpi=100)
        self.spect_fig.subplots_adjust(left=0, right=1, bottom=0, top=1, wspace=0, hspace=0)
        self.spect_canvas = FigureCanvasTkAgg(self.spect_fig, master=self.frame)  # A tk.DrawingArea.
        self.spect_canvas.get_tk_widget().grid(row=5, column=1, rowspan=4, columnspan=6)
        self.sp_axes = self.spect_fig.add_subplot()       # sp_axes is for spectrogram plot
        self.sp_axes.axis("off")                             # turn off axis labels for spectrogram plot


    def update_playback_speed(self, event):
        self.playback_speed = self.speed_scale.get()/100

    def plot_amp_chunk(self, x_list, y_list, color):    # used for real-time graphing while playing back
        self.amp_graph_canvas.create_line(*(tuple(zip(x_list, y_list))), fill=color, width='0.01m')
        self.amp_graph_canvas.move(self.marker_line_id, self.shift, 0)


    def record_file(self):
        # fs = self.fs if self.fs != None else self.DEFAULT_FRAMERATE              # Record at 44100 samples per second
        fs = self.DEFAULT_FRAMERATE              # Record at 48000 samples per second
        self.duration = model_audiograph.duration
        if self.duration == None:
            self.duration = self.DEFAULT_CLIP_LENGTH
        channels = 1
        color = "blue"
        format = pyaudio.paInt16
        # self.controls.recording_on()
        self.reset_graph()
        # instantiate pyaudio py_object and set up to stream sound data
        p = pyaudio.PyAudio()
        stream = p.open(format=format,
                        channels=channels,
                        rate=fs,
                        frames_per_buffer=self.RECORD_CHUNK,
                        input=True)

        frames = []  # Initialize array to store frames
        buffer_amplitude =  4000
        default_range_y = 32800
        MIN_Y = self.model_min_y - buffer_amplitude if self.model_min_y != None else -default_range_y
        MAX_Y = self.model_max_y + buffer_amplitude if self.model_max_y != None else default_range_y
        MIN_X, MAX_X = 0, self.duration * fs  # get min and max X values

        self.marker_line_id = self.amp_graph_canvas.create_line(0, 0, 0,
                                                                self.spect_canvas.get_tk_widget().winfo_height(),
                                                                fill='black', width='0.5m')
        self.shift = self.CHUNK * self.spect_canvas.get_tk_widget().winfo_height() * 1.0 / (MAX_X - MIN_X)

        for i in range(0, int(fs / self.CHUNK * self.duration)):
            data = stream.read(self.CHUNK)
            frames.append(data)
            sample_width = 2
            nb_samples = len(data) // sample_width         # calculate number of binary samples
            format = {1: "%db", 2: "<%dh", 4: "<%dl"}[sample_width] % nb_samples
            graph_data = struct.unpack(format, data)  # unpack binary data into structured data types
            x_width = self.spect_canvas.get_tk_widget().winfo_width()
            x_height = self.spect_canvas.get_tk_widget().winfo_height()
            x_list = np.array(range(i * self.CHUNK, i * self.CHUNK + self.CHUNK)) * x_width * 1.0 / (MAX_X - MIN_X)
            y_list = x_height - (np.array(graph_data) - MIN_Y) * x_height * 1.0 / (MAX_Y - MIN_Y)

            # start thread to graph wave form as audio file plays
            self.playgraph_thread = threading.Thread(target=self.plot_amp_chunk, args=(x_list, y_list, color))
            self.playgraph_thread.start()

        # Stop and close the stream
        stream.close()
        # Terminate the PortAudio interface
        p.terminate()
        self.controls.recording_off()

        # Save the recorded data as a WAV file
        # Open sound file  in write binary form.
        self.student_file = wave.open(self.student_filepath, 'wb')
        self.student_file.setnchannels(channels)
        self.student_file.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        self.student_file.setframerate(fs)
        self.student_file.writeframes(b''.join(frames))
        self.nothing_recorded = False
        self.student_file.close()

        self.nothing_recorded = False
        self.student_recording = True
        self.play_file()

    def set_framerate_duration(self, fs, duration):   # called by play_file
        self.fs, self.duration = fs, duration

    def set_y_range(self, min_y, max_y):
        self.model_min_y, self.model_max_y = min_y, max_y

    def spectral_centroid(self, graph_data, graph_ax):
        cent = librosa.feature.spectral_centroid(y=graph_data, sr=self.fs)
        S, phase = librosa.magphase(librosa.stft(y=graph_data))
        librosa.feature.spectral_centroid(S=S)

        freqs, times, mags = librosa.reassigned_spectrogram(graph_data, fill_nan=True)
        librosa.feature.spectral_centroid(S=np.abs(mags), freq=freqs)

        times = librosa.times_like(cent)
        librosa.display.specshow(librosa.amplitude_to_db(S, ref=np.max),
                                 y_axis='log', x_axis='time', ax=graph_ax)
        graph_ax.plot(times, cent.T, label='Spectral centroid', color='w')
        self.spect_canvas.get_tk_widget().grid(row=5, column=1, sticky=tk.NSEW)

    def play_file(self):
        # open file and reset sonograph field if necessary
        if self.student_recording == True:
            graph_y, sr = librosa.load(self.student_filepath)
            self.audio_file = wave.open(self.student_filepath, 'rb')    # open file for playing
        else:
            graph_y, sr = librosa.load(self.model_filepath)
            self.audio_file = wave.open(self.model_filepath, 'rb')    # open file for playing

        # initialize variables and attributes from audio file object
        self.reset_graph()                      # clear prior graph for a fresh plot
        n_frames, sample_width = self.audio_file.getnframes(), self.audio_file.getsampwidth()
        self.fs = framerate = self.audio_file.getframerate()
        self.duration = n_frames / framerate
        self.controls.playing_on()

        # if audio file is recordable student file, set duration to model file duration
        if self.record_object:
            self.record_object.set_framerate_duration(framerate, self.duration)

        # instantiate pyaudio py_object and set up to stream sound data
        py_object = pyaudio.PyAudio()
        audio_stream = py_object.open(format=py_object.get_format_from_width(sample_width),
                                      channels=self.audio_file.getnchannels(),
                                      rate=framerate, output=True)
        # use librosa libe for spectrogram
        self.spectral_centroid(graph_y, self.sp_axes)


        # read binary audio data and massage it into graphable format
        self.audio_data = self.audio_file.readframes(n_frames)
        nb_samples = len(self.audio_data) // sample_width         # calculate number of binary samples
        # turns binary data in audio data into a tuple of 66,466 ints in graph_data ... not sure how
        format = {1: "%db", 2: "<%dh", 4: "<%dl"}[sample_width] % nb_samples
        # unpack binary data into structured data type
        raw_graph_data = struct.unpack(format, self.audio_data)
        self.graph_data = tuple(0 if -50 <= num <= 50  or -10000 >= num >= 10000 else num for num in raw_graph_data)

        # these variables used to "frequency-color" wave form graph
        fourierTransform = np.fft.fft(self.graph_data)/len(self.graph_data)           # Normalize amplitud
        fourierTransform = fourierTransform[range(int(len(self.graph_data)/2))]       # Exclude sampling frequency
        fft = abs(fourierTransform)             # take absolute value since

        # get max and min of values in graph_data array
        max_amp = max(self.graph_data)
        min_amp = min(self.graph_data)
        # get max and min of values in fft value array
        max_fft_amp = max(fft)
        min_fft_amp = min(fft)
        norm_factor = (max_amp - min_amp)/(max_fft_amp - min_fft_amp)
        self.normalized_fft = (fft - min_fft_amp) * norm_factor + min_amp

        colors = ('black',
                  'fuchsia',
                  'darkorange',
                  'saddle brown',
                  'darkorange',
                  'orangered',
                  'red',
                  'goldenrod3',
                  'wheat3',
                  'darkorchid')

        def correlate(chunk, bin):
            chunk_weight = np.max(chunk) - np.min(chunk)
            bin_weight = np.max(bin) - np.min(bin)

            return abs(chunk_weight - bin_weight)

        # original bin quantiles:
        # freq_bins = [(color, bin) for color, bin in zip(colors, np.split(self.normalized_fft, [175, 700, 1600, 4001, 7001]))]
        # attempts to split bins based on mel frequencies:
        # freq_bounds = [51, 155, 273, 407, 560, 734, 933, 1158, 1415, 1707, 2039, 2418, 2848, 3339, 3896, 4531, 5254, 6076, 7012, 8077]
        # freq_bounds = [51,  734, 2418, 2848, 3339, 3896, 4531, 5254, 6076, 8077]
        # freq_bins = [(color, bin) for color, bin in zip(colors, np.split(self.normalized_fft, \
        #             [50, 287, 597, 1005, 1540, 2244, 3168, 4383, 5979, 8000]))]
        freq_bins = [(color, bin) for color, bin in zip(colors, np.split(self.normalized_fft,
                                                                         [51,  287, 1540, 2848, 3339, 3896, 4531, 5254, 6076, 8077]))]

        # get min and max Y values from graph_data array
        MIN_Y, MAX_Y = min(self.graph_data), max(self.graph_data)
        MIN_X, MAX_X = 0, self.duration * framerate  # get min and max X values
        if self.record_object:
            self.record_object.set_y_range(MIN_Y, MAX_Y)

        # chunk = self.CHUNK = int(bin_size * self.bin_chunk_ratio)
        chunk = self.CHUNK

        # form a list of lists based on chunks
        self.audio_data = [self.audio_data[i:i + chunk * 2] for i in range(0, len(self.audio_data), chunk * 2)]
        self.graph_data = [self.graph_data[i:i + chunk] for i in range(0, len(self.graph_data), chunk)]
        chunk_colors = []

        for graph_data_chunk in self.graph_data:
            color , min_distance = None, 99999999999
            for c, bin in freq_bins:
                distance = abs(correlate(graph_data_chunk, bin))
                if distance < min_distance:
                    min_distance = distance
                    color = c
            chunk_colors.append(color)

        # Normalize graph_data to fit window width and height, then initialize arrays
        X = []
        Y = []
        # i variable is the index of the current item while graph represents the actual graph data.
        for i, graph in enumerate(self.graph_data):
            # append to X[] an x val that's scaled to fit into a specific range on the canvas:
            #      ((FILE_POSITION + LEN(GRAPHCHUNK)) *  CANVAS_WIDTH) / Usable range of x values
            X.append(np.array(range(i * chunk, i * chunk + len(graph))) * self.canvas_width * 1.0 / (MAX_X - MIN_X))
            # append to array Y a new Y value that's scaled to fit the canvas:
            Y.append(self.canvas_height - (np.array(graph) - MIN_Y) * self.canvas_height * 1.0 / (MAX_Y - MIN_Y))
        self.marker_line_id = self.amp_graph_canvas.create_line(0, 0, 0, self.canvas_height, fill='black', width='0.5m')
        self.shift = chunk * self.canvas_width * 1.0 / (MAX_X - MIN_X)

        # play audio data while plotting audio waveform on a graph, chunk by chunk
        #       use enumerate function to iterate over a list of audio data along with three other lists X, Y, & chunk_colors.
        #       i = index while audio, x_list, y_list, and color are lists with corresponding values
        for i, (audio, x_list, y_list, color) in enumerate(zip(self.audio_data, X, Y, chunk_colors)):
            # ensure that the audio and graph playback are synchronized.
            time.sleep(0.25 * chunk / (self.audio_file.getframerate() * self.playback_speed))
            # set up thread to plot the amplitude of the audio chunk using the provided X and Y coordinates and color
            # self.playgraph_thread = threading.Thread(target=self.plot_amp_chunk, args=(x_list, y_list, color))
            self.playgraph_thread = threading.Thread(target=self.plot_amp_chunk, args=(x_list, y_list, color))
            self.playgraph_thread.start()
            # send current audio chunk to sound output
            audio_stream.write(audio)

        # Stop and close the stream
        audio_stream.stop_stream()
        audio_stream.close()
        # Terminate the PortAudio interface
        py_object.terminate()
        self.controls.playing_off()


    def start_play_thread(self, file_path):
        if self.student_recording == True:
            if self.play_thread and self.play_thread.is_alive():
                self.stop_playrecord_thread(self.student_filepath)
            if self.nothing_recorded == True:
                return
        else:
            if self.play_thread and self.play_thread.is_alive():
                self.stop_playrecord_thread(self.model_filepath)

        # start play_thread with currently selected file -- either student_file or model_file
        self.play_thread = threading.Thread(target=self.play_file)
        self.play_thread.start()


    def start_record_thread(self, file_path):
        self.nothing_recorded = True
        if file_path == None:
            return
        self.controls.recording_on()
        if self.record_thread and self.record_thread.is_alive():
            return
        # self.record_thread = thread_with_trace(target=self.record_file)
        self.record_thread = threading.Thread(target=self.record_file)
        self.record_thread.start()

    def stop_playrecord_thread(self, path):
        if self.play_thread and self.play_thread.is_alive():
            self.controls.playing_off()
            # self.play_thread.kill()
            return
        if self.record_thread and self.record_thread.is_alive():
            # self.stop()
            self.controls.recording_off()
            # self.record_thread.kill()

if __name__ == "__main__":
    SEPARATOR_WIDTH = 25
    SEPARATOR_HEIGHT = 25
    WINDOW_WIDTH = 1000
    WINDOW_HEIGHT = 900

    mainWindow = tk.Tk()
    mainWindow.title("accentprax project: audiographJUNE-Working")
    mainWindow.configure(background="light gray")
    mainWindow.geometry('{}x{}'.format(WINDOW_WIDTH, WINDOW_HEIGHT))
    separator_column = tk.Frame(mainWindow, background="light gray", width=SEPARATOR_WIDTH)
    separator_column.grid(row=0, column=0, rowspan=6)
    separator_row = tk.Frame(mainWindow, background="light gray", width=SEPARATOR_WIDTH)
    separator_row.grid(row=1, column=0, rowspan=6)
    model_frame = tk.Frame(mainWindow, background="light gray")
    model_frame.grid(row=0, column=1, columnspan=3)
    student_frame = tk.Frame(mainWindow, background="light gray")
    student_frame.grid(row=6, column=1, columnspan=3)
    record_flag = False
    record_object = None
    # record_flag = False
    # def __init__(self, root, UI_frame, width, height, record_flag):

    model_audiograph = AudioGraph(mainWindow, model_frame, False, None)
    student_audiograph = AudioGraph(mainWindow, student_frame, True, model_audiograph)

    mainWindow.mainloop()
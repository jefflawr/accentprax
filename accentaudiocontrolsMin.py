import tkinter


class AccentAudioControls:
    """ Class to provide audio control buttons

    Attributes:
        audio_file:     audio file to play
        audio_pointer:  location in audio file
        frame:
        play_button:
        stop_button:
        record_button:
        playing:

    Methods:
        __init__()
        set_controls_file(file) changes current open file variable to open file pointer argument
        play()                  starts playback, continues until another control button clicked
        stop()                  stops playback or recording
        record():               sets pointer to 0, starts recording
        has_record_button():    returns True or False to indicate presence of record_button
    """
    audio_file = None
    audio_pointer = 0
    frame = None
    play_button = None
    stop_button = None
    record_button = None
    # playing = False
    # recording = False
    image_list = {}
    BTN_WIDTH = 35

    def __init__(self, frame, can_record=True):
        self.image_list = {"stop": tkinter.PhotoImage(file="icons/stop_button.png"),
                           "play": tkinter.PhotoImage(file="icons/play_button.png"),
                           "playing": tkinter.PhotoImage(file="icons/play_button_light.png"),
                           "record": tkinter.PhotoImage(file="icons/record_button.png"),
                           "recording": tkinter.PhotoImage(file="icons/record_button_on.png"),
                           }
        self.BTN_WIDTH = 35
        self.playing = False
        self.recording = False
        self.frame = frame
        self.can_record = can_record
        # self.stop_button = tkinter.Button(self.frame, width=self.BTN_WIDTH, image=self.image_list["stop"])
        # self.stop_button.grid(row=0, column=0, sticky="nesw")
        if can_record == True:
            # self.record_button = tkinter.Button(self.frame, width=self.BTN_WIDTH, command=self.record,
            #                                    image=self.image_list["record"])
            self.record_button = tkinter.Button(self.frame, width=self.BTN_WIDTH, image=self.image_list["record"])
            self.record_button.grid(row=0, column=1, sticky="nesw")   # only column 1 if stop_button used
            # self.record_button.grid(row=0, column=0, sticky="nesw")
            # self.play_button = tkinter.Button(self.frame, width=self.BTN_WIDTH, command=self.play,
            #                                     image=self.image_list["play"])
            self.play_button = tkinter.Button(self.frame, width=self.BTN_WIDTH, image=self.image_list["play"])
            self.play_button.grid(row=0, column=2, sticky="nesw")    # only column 2 if stop_button used
            # self.play_button.grid(row=0, column=1, sticky="nesw")
        else:
            self.record_button = None
            # self.play_button = tkinter.Button(self.frame, width=BTN_WIDTH, command=self.play,
            #                                   image=self.image_list["play"])
            self.spacer_button = tkinter.Frame(self.frame, width=self.BTN_WIDTH, background="light gray")
            # self.spacer_button.grid(row=0, column=1, sticky="nesw")
            self.play_button = tkinter.Button(self.frame, width=self.BTN_WIDTH, image=self.image_list["play"])
            self.play_button.grid(row=0, column=2, sticky="nesw")    # only column 2 if stop_button used
            # self.play_button.grid(row=0, column=1, sticky="nesw")

    def get_file(self):
        return self.audio_file

    def set_file(self,file):
        self.audio_file = file

    def playing_on(self):
        self.playing = True
        self.play_button.configure(image=self.image_list["playing"])

    def playing_off(self):
        self.playing = False
        self.play_button.configure(image=self.image_list["play"])

    def recording_on(self):
        self.recording = True
        # print(self.image_list["recording"])
        self.record_button.configure(image=self.image_list["recording"])

    def recording_off(self):
        self.recording = False
        # print(self.image_list["record"])
        self.record_button.configure(image=self.image_list["record"])

    def stop_process(self, process_thread):
        process_thread.stop()


import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

GST_PAD_LINK_OK = 0

audio_convertor = None
video_convertor = None

def pad_add(src_pad, sink_pad):
    if sink_pad.is_linked():
        print("Error, sink_pad is already linked to another pad")
        return

    connection_result:Gst.PadLinkReturn = src_pad.link(sink_pad)
    if GST_PAD_LINK_OK != connection_result:
        print("Error while trying to link pad")
        return

    print("Successful connection between source pad and sink pad of audio convertor")

def pad_added_handler(source, new_pad):
    new_pad_name = new_pad.get_current_caps().get_structure(0).get_name()
    if new_pad_name.startswith("audio/x-raw"):
        pad_add(new_pad, audio_convertor.get_static_pad("sink"))
    elif new_pad_name.startswith("video/x-raw"):
        pad_add(new_pad, video_convertor.get_static_pad("sink"))
    else:
        print(f"Bad pad request name: {new_pad_name}")
    

def tutorial_main():
    global audio_convertor, video_convertor
    Gst.init(None)

    pipeline = Gst.Pipeline()

    # Creating GElement
    source = Gst.ElementFactory.make("uridecodebin")

    audio_convertor = Gst.ElementFactory.make("audioconvert")
    video_convertor = Gst.ElementFactory.make("videoconvert")
    audio_resample = Gst.ElementFactory.make("audioresample")
    video_resample = Gst.ElementFactory.make("videoresample")

    sink_audio = Gst.ElementFactory.make("autoaudiosink")
    sink_video = Gst.ElementFactory.make("autovideosink")

    # Add GElement in the pipeline
    pipeline.add(source)
    pipeline.add(audio_convertor)
    pipeline.add(video_convertor)
    pipeline.add(audio_resample)
    pipeline.add(sink_audio)
    pipeline.add(sink_video)

    # Link GElement in the pipeline
    #source.link(audio_convertor)
    audio_convertor.link(audio_resample)
    audio_resample.link(sink_audio)
    video_convertor.link(sink_video)
    

    # Ajout du lien de la video dans la source
    uri_file_name = Gst.filename_to_uri("../../res/endoscopy.mp4")
    source.set_property("uri", uri_file_name)

    # Ajout d'un signal pour détecter un élément
    source.connect("pad-added", pad_added_handler)

    # On démarre la pipeline
    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        print("Unable to set the pipeline to the playing state.")
        

    bus = pipeline.get_bus()
    stream_ended = False

    while not stream_ended:
            

        msg = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE, Gst.MessageType.ERROR | Gst.MessageType.EOS)

        if msg is not None:
            if msg.type == Gst.MessageType.ERROR:
                err, debug_info = msg.parse_error()
                print("Error received from element {}: {}".format(msg.src.get_name(), err.message))
                print("Debugging information: {}".format(debug_info if debug_info else "none"))
                stream_ended = True
            elif msg.type == Gst.MessageType.EOS:
                print("End-Of-Stream reached.")
                stream_ended = True
            elif msg.type == Gst.MessageType.StateChangeReturn:
                print("State changed")
            else:
                print("Unexpected message received.")
    pipeline.set_state(Gst.State.NULL)

def main():
    tutorial_main()

if __name__ == '__main__':
    main()

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

stream_playing = None
end_stream_reading = False
stream_duration = Gst.CLOCK_TIME_NONE

seek_enabled = False
seek_done = False

playbin = None

def play_stream():
    global seek_done, stream_duration

    if stream_playing:

        # Query the position in the stream
        _, current_time = playbin.query_position(Gst.Format.TIME)
        if not current_time:
            print("Can't query the current_time of the stream")
            exit()

        # Query the duration of the stream
        if stream_duration == Gst.CLOCK_TIME_NONE:
            _, stream_duration = playbin.query_duration(Gst.Format.TIME)
            if not stream_duration:
                print("Can query the duration of the stream")

        print(f"{stream_duration=}")
        print(f"{current_time=}")

        if seek_enabled and not seek_done and current_time > 10 * Gst.SECOND:
            print(f"Reaching 10s, performing seek...")
            playbin.seek_simple(Gst.Format.TIME,
                                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                                30 * Gst.SECOND)
            seek_done = True

def handle_error_message(error_message):
    global end_stream_reading, stream_duration, stream_playing, seek_enabled

    if error_message.type == Gst.MessageType.ERROR:
        err, debug_info = error_message.parse_error()
        print("Error received from element {}: {}".format(error_message.src.get_name(), err.message))
        print("Debugging information: {}".format(debug_info if debug_info else "none"))
        end_stream_reading = True
    elif error_message.type == Gst.MessageType.EOS:
        print("End-Of-Stream reached.")
        end_stream_reading = True
    elif error_message.type == Gst.MessageType.DURATION_CHANGED:
        stream_duration = Gst.CLOCK_TIME_NONE
        print("duration changed")
    elif error_message.type == Gst.MessageType.STATE_CHANGED:
        if error_message.src == playbin:
            print("State changed")
            old_state, new_state, pending_state = error_message.parse_state_changed()
            print(f"Pipeline state changed from {old_state} to {new_state}:")
            stream_playing = (new_state == Gst.State.PLAYING)

            if stream_playing:
                # Demande si le seeking peut être effectué grâce au Query
                query = Gst.Query.new_seeking(Gst.Format.TIME)
                if playbin.query(query):
                    _, seek_enabled, start, end = query.parse_seeking()
                    if seek_enabled:
                        print("Seeking is ENABLED from {} to {}".format(start, end))
                    else:
                        print("Seeking is DISABLED for this stream.")
                else:
                    print("Seeking query failed.")
                    
    else:
        print("Unexpected message received.")

def main():
    global playbin

    Gst.init()

    playbin = Gst.ElementFactory.make("playbin")

    if playbin is None:
        print(f"{playbin=}")
        exit(1)

    playbin.set_property("uri", Gst.filename_to_uri("../../res/endoscopy.mp4"))


    res = playbin.set_state(Gst.State.PLAYING)
    if res == Gst.StateChangeReturn.FAILURE:
        print("Fail to play the stream")
        exit(1)

    bus = playbin.get_bus()

    while not end_stream_reading:
        # Affiche le flux pendent 100ms laisse la main
        error_message = bus.timed_pop_filtered(100 * Gst.MSECOND,
                                Gst.MessageType.ERROR | Gst.MessageType.EOS | Gst.MessageType.STATE_CHANGED | Gst.MessageType.DURATION_CHANGED)

        if error_message != None:
            handle_error_message(error_message)
        else:
            play_stream()
        print()                



if __name__ == "__main__":
    main()
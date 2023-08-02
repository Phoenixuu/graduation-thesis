import gi
gi.require_version("Gst", "1.0")
gi.require_version("Gtk", "3.0")
gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, Gtk, GLib, GdkX11, GstVideo, Gdk
import cairo
import sys
import pyds
from time import time

# https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_troubleshooting.html#the-deepstream-application-is-running-slowly
# https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Performance.html#deepstream-reference-model-and-tracker

# Gst global variables
playbin:Gst.Bin = None
slider_update_signal_id = -1
record_duration = Gst.CLOCK_TIME_NONE
streaming_state = Gst.State.NULL

pipeline = None
src = None
convert = None
sink = None

main_window = None

# Gtk global variables
slider:Gtk.Scale = None

fps_amoumt = 0
last_second = time()

last_body_part_id = -1
last_body_part_name = None

def osd_sink_pad_buffer_probe(pad,info,u_data):
    global fps_amoumt, last_second, last_body_part_id, last_body_part_name

    current_time = time()
    if int(last_second) == int(current_time):
        fps_amoumt += 1
    else:
        print(f"fps: {fps_amoumt}")
        fps_amoumt = 1
        last_second = current_time

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return
    
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    
    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        #print("Reading frame")
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            print("Error on convert l_frame to frame meta")
            break
        if frame_meta is None:
            l_frame = l_frame.next
            continue

        l_obj = frame_meta.obj_meta_list
        while l_obj is not None:
            #print("Reading object")
            try:
                # Casting l_obj.data to pyds.NvDsObjectMeta
                obj_meta=pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                print("Error on convert l_obj to object meta")
                break
            if obj_meta is None:
                l_obj = l_obj.next
                continue

            # Hide bounding box
            obj_meta.rect_params.border_color.set(0.0, 0.0, 0.0, 0.0)

            l_class = obj_meta.classifier_meta_list
            while l_class is not None:
                try:
                    class_meta = pyds.NvDsClassifierMeta.cast(l_class.data)
                except StopIteration:
                    print("Error on convert l_class to class meta")
                    break
                if class_meta is None:
                    l_class = l_class.next
                    continue

                label_i = 0
                l_label = class_meta.label_info_list
                while (l_class is not None) and (label_i < class_meta.num_labels):
                    try:
                        label_info = pyds.NvDsLabelInfo.cast(l_label.data)
                    except StopIteration:
                        print("Error on convert l_label to label info")
                        break

                    if label_info is not None:
                        #print(f"Label id = {label_info.label_id}")
                        last_body_part_id = label_info.result_class_id
                        last_body_part_name = label_info.result_label
                        #print(f"result class id = {label_info.result_class_id}")
                        #print(f"result label = {label_info.result_label}")
                        pass

                    label_i += 1
                    l_label = l_label.next

                l_class = l_class.next

            # Remove the label of the current object
            pyds.nvds_remove_obj_meta_from_frame(frame_meta, obj_meta)
            
            l_obj = l_obj.next
        
        
        if last_body_part_id != -1:
            # Acquiring a display meta object. The memory ownership remains in
            # the C code so downstream plugins can still access it. Otherwise
            # the garbage collector will claim it when this probe function exits.
            display_meta=pyds.nvds_acquire_display_meta_from_pool(batch_meta)
            display_meta.num_labels = 1
            py_nvosd_text_params = display_meta.text_params[0]
            # Setting display text to be shown on screen
            # Note that the pyds module allocates a buffer for the string, and the
            # memory will not be claimed by the garbage collector.
            # Reading the display_text field here will return the C address of the
            # allocated string. Use pyds.get_string() to get the string content.
            py_nvosd_text_params.display_text = last_body_part_name

            # Now set the offsets where the string should appear
            py_nvosd_text_params.x_offset = 0
            py_nvosd_text_params.y_offset = 60

            # Font , font-color and font-size
            py_nvosd_text_params.font_params.font_name = "Serif"
            py_nvosd_text_params.font_params.font_size = 25
            # set(red, green, blue, alpha); set to White
            py_nvosd_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)

            # Text background color
            py_nvosd_text_params.set_bg_clr = 1
            # set(red, green, blue, alpha); set to Black
            py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)
            # Using pyds.get_string() to get display_text as string
            #print(pyds.get_string(py_nvosd_text_params.display_text))
            pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
        
        l_frame = l_frame.next

    return Gst.PadProbeReturn.OK

def pad_add(src_pad, sink_pad):
    if sink_pad.is_linked():
        print("Error, sink_pad is already linked to another pad")
        return

    connection_result:Gst.PadLinkReturn = src_pad.link(sink_pad)
    if Gst.PadLinkReturn.OK != connection_result:
        print("Error while trying to link pad")
        return

    print("Successful connection between source pad and sink pad of video convertor")

def pad_added_handler(source, new_pad):
        new_pad_name = new_pad.get_current_caps().get_structure(0).get_name()
        print(new_pad_name)
        if new_pad_name.startswith("video/x-raw"):
            pad_add(new_pad, convert.get_static_pad("sink"))
        else:
            print(f"Bad pad request name: {new_pad_name}")

def error_cb(bus:Gst.Bus, msg:Gst.Message):
    """
    Called when an error appear on the stream

    Args:
        bus (Gst.Bus)
        msg (Gst.Message)
    """
    err, debug_info = msg.parse_error()
    print("Error received from element {}: {}".format(msg.src.get_name(), err.message))
    print("Debugging information: {}".format(debug_info if debug_info else "none"))

    # Set the state of the pipeline to READY
    # (and stop reading the video)
    pipeline.set_state(Gst.State.READY)

def eos_cb(bus:Gst.Bus, msg:Gst.Message):
    """
    Called when the end-of-stream appear

    Args:
        bus (Gst.Bus)
        msg (Gst.Message)
    """
    print("End-Of-Stream reached.")
    pipeline.set_state(Gst.State.READY)

def state_changed_cb(bus:Gst.Bus, msg:Gst.Message):
    """
    Called when the state of the pipeline change

    Args:
        bus (Gst.Bus)
        msg (Gst.Message)
    """
    global streaming_state
    old_state, new_state, pending_state = msg.parse_state_changed()

    if msg.src == pipeline:
        streaming_state = new_state
        print("State set to", Gst.Element.state_get_name(new_state))

        if old_state == Gst.State.READY and new_state == Gst.State.PAUSED:
            # For extra responsiveness, we refresh the GUI as soon as we reach the PAUSED state
            refresh_ui()

# Fonctions Gtk
def on_window_close(window:Gtk.Window, event:Gdk.Event):
    """
    Called when the user close the window

    Args:
        window (Gtk.Window)
        event (Gdk.Event)
    """
    stop_cb(None)
    Gtk.main_quit()


def play_cb(button:Gtk.Button):
    """
    Called when the PLAY button is clicked

    Args:
        button (Gtk.Button)
    """
    pipeline.set_state(Gst.State.PLAYING)

def pause_cb(button:Gtk.Button):
    """
    Called when the PAUSE button is clicked

    Args:
        button (Gtk.Button)
    """
    pipeline.set_state(Gst.State.PAUSED)

def stop_cb(button:Gtk.Button):
    """
    Called when the STOP button is clicked

    Args:
        button (Gtk.Button)
    """
    pipeline.set_state(Gst.State.READY)

def slider_cb(gtk_range:Gtk.Range):
    """
    Called when the cursor of the slider
    changes position. We perform a seek 
    to the new position and draw it on 
    the screen.

    Args:
        button (Gtk.Button)
    """
    slider_value = gtk_range.get_value()
    pipeline.seek_simple(Gst.Format.TIME,
                        Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 
                        int(slider_value * Gst.SECOND))


def realize_cb(widget:Gtk.Widget):
    """ 
    Called when the widget `video_window`
    (Gtk.DrawingArea) is init on the window
    display.

    Args:
        widget (Gtk.Widget): le `video_window`,
            ici de type Gtk.DrawingArea
    """
    window = widget.get_window()

    if not window.ensure_native():
        print("Couldn't create native window needed for GstVideoOverlay!")


    window_handle = None
    if sys.platform == "win32":
        window_handle = window.get_window().handle
    elif sys.platform == "darwin":
        window_handle = window.get_window().get_nsview()
    elif sys.platform.startswith("linux"):
        window_handle = window.get_xid()
    else:
        print(f"Platform \"{sys.platform}\" is unknown")

    sink.set_window_handle(window_handle)

def draw_cb(widget:Gtk.Widget, cr:cairo.Context):
    """
    Called when the `video_window` need to be
    redraw.
    Used for example when the drawing area
    is shown for the first time, when the window 
    is resized and when a his content need to
    be updated.
    
    When there is data flow (in the PAUSED
    and PLAYING states) the video sink takes
    care of refreshing the content of the 
    video window. In the other cases, 
    however, it will not, so we have to do it. 

    Args:
        widget (Gtk.Widget): le `video_window`,
            ici de type Gtk.DrawingArea
        cr (cairo.Context)
    """
    if streaming_state < Gst.State.PAUSED:
        allocation = widget.get_allocation()

        # Cairo is a 2D graphics library used to clean the video window
        cr.set_source_rgb(0, 0, 0)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()

def refresh_ui() -> bool:
    """
    Called each second by GLib to
    refresh the Gtk image.
    

    We update the position of the slider cursor Gtk 
    slider so that it is consistent with the duration 
    since which the video was started.
    (On met à jour la position du curseur du slider
    Gtk pour qu'elle soit cohérente avec la durée
    depuis laquelle la vidéo a été démarré.)

    Return: 
        True from this function will keep 
        it called in the future. If we return False, 
        the timer will be removed.
    """
    global record_duration, slider

    if streaming_state < Gst.State.PAUSED:
        return True

    if record_duration == Gst.CLOCK_TIME_NONE:
        _, record_duration = pipeline.query_duration(Gst.Format.TIME)
        if not record_duration or record_duration == Gst.CLOCK_TIME_NONE:
            print("Could not query current duration.")
            return False
        else:
            # Init the range of the slider 
            slider.set_range(0, float(record_duration) / Gst.SECOND)

    # Update the slider cursor by the current time of
    # the video
    current_time = pipeline.query_position(Gst.Format.TIME)
    if not current_time:
        print("Can't query the position in the streaming")
    else:
        slider.handler_block(slider_update_signal_id)
        slider.set_value(current_time[1] / Gst.SECOND)
        slider.handler_unblock(slider_update_signal_id)
        
    return True

def create_ui():
    """
    Create all Gtk widgets
    """
    global slider, slider_update_signal_id, main_window

    main_window = Gtk.Window()
    main_window.connect("delete-event", on_window_close)

    video_window = Gtk.DrawingArea()
    # La fonction realize_cb sera appelée
    # lorsque le widget `video_window`
    # est instancié sur un display (window)
    video_window.connect("realize", realize_cb)
    # La fonction draw_cb sera appelée
    # dès que le `video_window` a besoin
    # d'être redessinée.
    # Utilisé lorsque la zone de dessin est 
    # affichée pour la première fois, lorsqu'elle 
    # est redimensionnée ou lorsqu'une partie 
    # de son contenu doit être mise à jour.
    video_window.connect("draw", draw_cb)


    # Widgets
    play_button = Gtk.Button.new_from_icon_name("media-playback-start", Gtk.IconSize.SMALL_TOOLBAR)
    play_button.connect("clicked", play_cb)

    pause_button = Gtk.Button.new_from_icon_name("media-playback-pause", Gtk.IconSize.SMALL_TOOLBAR)
    pause_button.connect("clicked", pause_cb)

    stop_button = Gtk.Button.new_from_icon_name("media-playback-stop", Gtk.IconSize.SMALL_TOOLBAR)
    stop_button.connect("clicked", stop_cb)

    slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
    slider.set_draw_value(False)
    # On garde on mémoire le connecteur pour
    # le désactiver lorsque l'utilisateur déplacera
    # le curseur du slider ou alors lorsqu'il se
    # déplacera tout seul et qu'il faudra pas faire
    # de recherche
    slider_update_signal_id = slider.connect("value-changed", slider_cb)

    # Create widgets
    controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    controls.pack_start(play_button, False, False, 2)
    controls.pack_start(pause_button, False, False, 2)
    controls.pack_start(stop_button, False, False, 2)
    controls.pack_start(slider, True, True, 2)

    # Packing widgets
    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    main_box.pack_start(video_window, True, True, 0)
    main_box.pack_start(controls, False, False, 0)

    # Setting window
    main_window.add(main_box)
    main_window.set_default_size(640, 480)

    # La fonction `realize_cb` sera appelée lorsque
    # la fonction `main_window.show_all()` sera
    # executée
    main_window.show_all()

def main():
    global pipeline, src, convert, sink

    # Gtk & Gst init
    Gtk.init()
    Gst.init(None)

    pipeline = Gst.parse_launch("""
        filesrc location=../../res/endoscopy.mp4 ! 
        qtdemux name=demux demux.video_0 ! 
        queue ! 
        h264parse ! 
        nvv4l2decoder ! 
        m.sink_0 nvstreammux name=m batch-size=1 width=1280 height=1024 ! 
        nvvideoconvert !
        nvinfer !
        nvdsosd ! 
        nvegltransform ! 
        nveglglessink name=sink
    """)

    infer = pipeline.get_by_name("nvinfer0")
    infer.set_property("config-file-path", "./classifier_digestive_parts_pgie_config.txt")


    osd = pipeline.get_by_name("nvdsosd0")
    #osd.set_property('display-text', 1)

    sink = pipeline.get_by_name("sink")

    assert pipeline is not None
    
    # Create all Gtk widgets
    create_ui()

    bus = pipeline.get_bus()
    # Configure le bus pour qu'il puisse connecter
    # nos callback à des signaux
    # C'est mieux que la fonction `gst_bus_add_watch`
    # car cette dernière envoie tous les messages
    # d'erreur existant
    bus.add_signal_watch()
    bus.connect("message::error", error_cb)
    bus.connect("message::eos", eos_cb)
    # Ce signal est émis lorsque l'état de la lecture change. 
    # Il peut être utilisé pour détecter les transitions 
    # d'état, telles que le passage de l'état "PLAYING" 
    # à l'état "PAUSED" ou à l'état "STOPPED"
    bus.connect("message::state-changed", state_changed_cb)
    # Signal custom qu'on crée pour poster
    # un message sur le bus depuis un thread Gtk
    # pour operer depuis le thread Gst
    
    osdsinkpad = osd.get_static_pad("sink")
    if not osdsinkpad:
        sys.stderr.write(" Unable to get sink pad of nvosd \n")

    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

    # Start playing
    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        sys.stderr.write("Unable to set the pipeline to the playing state.\n")
        return -1
    

    # Register a function that GLib will call every second
    GLib.timeout_add_seconds(1, refresh_ui)

    Gtk.main()

    pipeline.set_state(Gst.State.NULL)

if __name__ == "__main__":
    main()

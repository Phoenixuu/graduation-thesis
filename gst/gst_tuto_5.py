import gi
gi.require_version("Gst", "1.0")
gi.require_version("Gtk", "3.0")
gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, Gtk, GLib, GdkX11, GstVideo, Gdk
import cairo
import sys

# Other way to do it: https://github.com/gkralik/python-gst-tutorial/blob/master/basic-tutorial-5.py

# Gst global variables
playbin:Gst.Bin = None
slider_update_signal_id = -1
record_duration = Gst.CLOCK_TIME_NONE
streaming_state = Gst.State.NULL

# Gtk global variables
slider:Gtk.Scale = None


# Fonctions Gst
def tags_cb(playbin:Gst.Bin, stream:int):
    """
    Args:
        playbin (Gst.Bin)
        stream (int)
    """
    structure = Gst.Structure.new_empty("tags-changed")
    message = Gst.Message.new_application(playbin, structure)
    playbin.post_message(message)

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
    playbin.set_state(Gst.State.READY)

def eos_cb(bus:Gst.Bus, msg:Gst.Message):
    """
    Called when the end-of-stream appear

    Args:
        bus (Gst.Bus)
        msg (Gst.Message)
    """
    print("End-Of-Stream reached.")
    playbin.set_state(Gst.State.READY)

def state_changed_cb(bus:Gst.Bus, msg:Gst.Message):
    """
    Called when the state of the pipeline change

    Args:
        bus (Gst.Bus)
        msg (Gst.Message)
    """
    global streaming_state
    old_state, new_state, pending_state = msg.parse_state_changed()

    if msg.src == playbin:
        streaming_state = new_state
        print("State set to", Gst.Element.state_get_name(new_state))

        if old_state == Gst.State.READY and new_state == Gst.State.PAUSED:
            # For extra responsiveness, we refresh the GUI as soon as we reach the PAUSED state
            refresh_ui()

def application_cb(bus:Gst.Bus, message:Gst.Message):
    """
    This function is called when the custom signal
    'tags-changed' message is posted on the bus.
    Here we retrieve the message posted by the 
    tags_cb callback.

    Args:
        bus (gst.Bus)
        message (Gst.Message)
    """
    if message.get_structure().get_name() == "tag-changed":
        print("application cb")

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
    playbin.set_state(Gst.State.PLAYING)

def pause_cb(button:Gtk.Button):
    """
    Called when the PAUSE button is clicked

    Args:
        button (Gtk.Button)
    """
    playbin.set_state(Gst.State.PAUSED)

def stop_cb(button:Gtk.Button):
    """
    Called when the STOP button is clicked

    Args:
        button (Gtk.Button)
    """
    playbin.set_state(Gst.State.READY)

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
    playbin.seek_simple(Gst.Format.TIME,
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

    playbin.set_window_handle(window_handle)

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

    if streaming_state >= Gst.State.PAUSED:
        return True

    if record_duration == Gst.CLOCK_TIME_NONE:
        _, record_duration = playbin.query_duration(Gst.Format.TIME)
        if not record_duration or record_duration == Gst.CLOCK_TIME_NONE:
            print("Could not query current duration.")
            return False
        else:
            # Init the range of the slider 
            slider.set_range(0, float(record_duration) / Gst.SECOND)

    # Update the slider cursor by the current time of
    # the video
    current_time = playbin.query_position(Gst.Format.TIME)
    if not current_time:
        print("Can't query the position in the streaming")
    else:
        slider.handler_block(slider_update_signal_id)
        slider.set_value(current_time[1] / Gst.SECOND)
        slider.handler_unblock(slider_update_signal_id)
        print("Current time slider has been updated")
        
    return True

def create_ui():
    """
    Create all Gtk widgets
    """
    global slider, slider_update_signal_id

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
    global playbin

    # Gtk & Gst init
    Gtk.init()
    Gst.init(None)

    # playbin creation
    playbin = Gst.ElementFactory.make("playbin")
    assert playbin is not None

    # playbin settings
    uri_file_name = Gst.filename_to_uri("../../res/endoscopy.mp4")
    playbin.set_property("uri", uri_file_name)

    # La fonction `connect` permet de connecter
    # un signal reçu par l'élément `playbin` à un
    # callback.
    #
    # Le tag/signal `video-tags-changed` fait
    # référence à un événement qui se produit lorsque
    # les tags/metadonnées de la video changent.
    #playbin.connect("video-tags-changed", tags_cb)
    
    # Create all Gtk widgets
    create_ui()

    bus = playbin.get_bus()
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
    #bus.connect("message::application", application_cb)
    
    # Start playing
    ret = playbin.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        sys.stderr.write("Unable to set the pipeline to the playing state.\n")
        playbin.unref()
        return -1

    # Register a function that GLib will call every second
    GLib.timeout_add_seconds(1, refresh_ui)

    Gtk.main()

    playbin.set_state(Gst.State.NULL)

if __name__ == "__main__":
    main()

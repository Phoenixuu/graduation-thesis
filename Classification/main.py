import os
import gi
import sys
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
import platform

import pyds

def bus_call(bus, message, loop):
    t = message.type
    if t == Gst.MessageType.EOS:
        sys.stdout.write("End-of-stream\n")
        loop.quit()
    elif t == Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        sys.stderr.write("Warning: %s: %s\n" % (err, debug))
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        sys.stderr.write("Error: %s: %s\n" % (err, debug))
        loop.quit()
    return True

def is_aarch64():
    return platform.uname()[4] == 'aarch64'

#sys.path.append('/opt/nvidia/deepstream/deepstream/lib')

SINK_TYPE_GL = "gl"
SINK_TYPE_AUTO = "auto"


CLASSEA = 0
CLASSEB = 1
CLASSEC = 2
CLASSED = 3
CLASSEE = 4
CLASSEF = 5
CLASSEG = 6
CLASSEH = 7
CLASSEI = 8
CLASSEJ = 9


def osd_sink_pad_buffer_probe(pad,info,u_data):
    frame_number=0
    #Intiallizing object counter with 0.
    obj_counter = {
        CLASSEA : 0,
        CLASSEB : 1,
        CLASSEC : 2,
        CLASSED : 3,
        CLASSEE : 4,
        CLASSEF : 5,
        CLASSEG : 6,
        CLASSEH : 7,
        CLASSEI : 8,
        CLASSEJ : 9
    }
    num_rects=0

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        try:
            # Note that l_frame.data needs a cast to pyds.NvDsFrameMeta
            # The casting is done by pyds.NvDsFrameMeta.cast()
            # The casting also keeps ownership of the underlying memory
            # in the C code, so the Python garbage collector will leave
            # it alone.
           frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break

        frame_number=frame_meta.frame_num
        num_rects = frame_meta.num_obj_meta
        l_obj=frame_meta.obj_meta_list
        while l_obj is not None:
            try:
                # Casting l_obj.data to pyds.NvDsObjectMeta
                obj_meta=pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break
            obj_counter[obj_meta.class_id] += 1
            try: 
                l_obj=l_obj.next
            except StopIteration:
                break

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
        py_nvosd_text_params.display_text = "Frame Number={} Number of Objects={} Vehicle_count={} Person_count={}".format(frame_number, num_rects, obj_counter[CLASSEA], obj_counter[CLASSEB])

        # Now set the offsets where the string should appear
        py_nvosd_text_params.x_offset = 10
        py_nvosd_text_params.y_offset = 12

        # Font , font-color and font-size
        py_nvosd_text_params.font_params.font_name = "Serif"
        py_nvosd_text_params.font_params.font_size = 10
        # set(red, green, blue, alpha); set to White
        py_nvosd_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)

        # Text background color
        py_nvosd_text_params.set_bg_clr = 1
        # set(red, green, blue, alpha); set to Black
        py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)
        # Using pyds.get_string() to get display_text as string
        print(pyds.get_string(py_nvosd_text_params.display_text))
        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
        try:
            l_frame=l_frame.next
        except StopIteration:
            break
			
    return Gst.PadProbeReturn.OK

def create_element_factory(g_element_factory_name:str):
    g_element_factory = Gst.ElementFactory.make(g_element_factory_name)
    if g_element_factory is None:
        print(f"Unable to create element \"{g_element_factory_name}\"", file=sys.stderr)
        exit(1)
    return g_element_factory

def main(sink_type:str):

    Gst.init(None)

    pipeline = Gst.Pipeline()
    assert pipeline is not None

    # Create GElement Factory
    #source = create_element_factory("v4l2src")
    source = Gst.ElementFactory.make("uridecodebin")
    caps_filter_src = create_element_factory("capsfilter")
    video_conv_src = create_element_factory("videoconvert")
    nv_video_conv_src = create_element_factory("nvvideoconvert")
    caps_filter_video_conf = create_element_factory("capsfilter")
    streammux = create_element_factory("nvstreammux")
    pgie = create_element_factory("nvinfer")
    nv_video_conv = create_element_factory("nvvideoconvert")
    nvosd = create_element_factory("nvdsosd")

    sink = None
    if sink_type == SINK_TYPE_AUTO:
        sink = create_element_factory("nv3dsink")
    elif sink_type == SINK_TYPE_GL:
        sink = create_element_factory("nveglglessink")
    else:
        print(f"Unknown sink type \"{sink_type}\".")
        return

    caps_filter_src.set_property('caps', Gst.Caps.from_string("video/x-raw, framerate=30/1"))
    caps_filter_video_conf.set_property('caps', Gst.Caps.from_string("video/x-raw(memory:NVMM)"))
    #source.set_property('device', "/dev/video0")
    uri_file_name = Gst.filename_to_uri("../res/endoscopy.mp4")
    source.set_property("uri", uri_file_name)
    streammux.set_property('width', 1280)
    streammux.set_property('height', 1024)
    streammux.set_property('batch-size', 1)
    streammux.set_property('batched-push-timeout', 4000000)
    pgie.set_property('config-file-path', "endoscopy_pgie_config.txt")
    # Set sync = false to avoid late frame drops at the display-sink
    sink.set_property('sync', False)

    pipeline.add(source)
    pipeline.add(caps_filter_src)
    pipeline.add(video_conv_src)
    pipeline.add(nv_video_conv_src)
    pipeline.add(caps_filter_video_conf)
    pipeline.add(streammux)
    pipeline.add(pgie)
    pipeline.add(nv_video_conv)
    pipeline.add(nvosd)
    pipeline.add(sink)


    source.link(caps_filter_src)
    caps_filter_src.link(video_conv_src)
    video_conv_src.link(nv_video_conv_src)
    nv_video_conv_src.link(caps_filter_video_conf)

    sinkpad = streammux.get_request_pad("sink_0")
    if not sinkpad:
        sys.stderr.write(" Unable to get the sink pad of streammux \n")
    srcpad = caps_filter_video_conf.get_static_pad("src")
    if not srcpad:
        sys.stderr.write(" Unable to get source pad of caps_vidconvsrc \n")
    srcpad.link(sinkpad)
    streammux.link(pgie)
    pgie.link(nv_video_conv)
    nv_video_conv.link(nvosd)
    nvosd.link(sink)


    # create an event loop and feed gstreamer bus mesages to it
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)

    # Lets add probe to get informed of the meta data generated, we add probe to
    # the sink pad of the osd element, since by that time, the buffer would have
    # had got all the metadata.
    osdsinkpad = nvosd.get_static_pad("sink")
    if not osdsinkpad:
        sys.stderr.write(" Unable to get sink pad of nvosd \n")

    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

    # start play back and listen to events
    print("Starting pipeline \n")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    pipeline.set_state(Gst.State.NULL)

if __name__ == "__main__":
    if len(sys.argv) < 2 or (sys.argv[1] != SINK_TYPE_AUTO and sys.argv[1] != SINK_TYPE_GL):
        print(f"Wrong command usage:")
        print(f"Usage: {sys.argv[0]} <{SINK_TYPE_AUTO}|{SINK_TYPE_GL}>")
        exit(1)

    main(sys.argv[1])
import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import pyds
import numpy as np
from time import time

PGIE_CLASS_ID_LARYNX = 0
PGIE_CLASS_ID_SOPHAGUS = 1
PGIE_CLASS_ID_CARDIA = 2
PGIE_CLASS_ID_BODY = 3
PGIE_CLASS_ID_FUNDUS = 4
PGIE_CLASS_ID_PYLORUS = 5
PGIE_CLASS_ID_GREATCURVATURE = 6
PGIE_CLASS_ID_LESSERCURVATURE = 7
PGIE_CLASS_ID_DUODENUMBULB = 8
PGIE_CLASS_ID_DUODENUM = 9

video_queue = None

last_time = time()
fps = 0


def osd_sink_pad_buffer_probe(pad,info,u_data):

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return
    
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    
    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        print("Reading frame")
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
            print("Reading object")
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
                        print(f"Label id = {label_info.label_id}")
                        print(f"result class id = {label_info.result_class_id}")
                        print(f"result label = {label_info.result_label}")

                    label_i += 1
                    l_label = l_label.next

                l_class = l_class.next

            l_obj = l_obj.next

        l_frame = l_frame.next

    return Gst.PadProbeReturn.OK

def on_message(bus, message):
    t = message.type
    if t == Gst.MessageType.EOS:
        print("End of file")
        pipeline.set_state(Gst.State.NULL)
        sys.exit(0)
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print("pipeline error:", err)
        print("Debug information :", debug)
        pipeline.set_state(Gst.State.NULL)
        sys.exit(1)

if __name__ == '__main__':
    Gst.init(None)

    pipeline = Gst.parse_launch("""
        filesrc location=../res/endoscopy.mp4 ! 
        qtdemux name=demux demux.video_0 ! 
        queue ! 
        h264parse ! 
        nvv4l2decoder ! 
        m.sink_0 nvstreammux name=m batch-size=1 width=1280 height=1024 ! 
        nvvideoconvert !
        nvinfer !
        nvdsosd ! 
        nvegltransform ! 
        nveglglessink
    """)

    nvinfer = pipeline.get_by_name("nvinfer0")
    nvinfer.set_property("config-file-path", "./endoscopy_pgie_config.txt")

    nvdsosd = pipeline.get_by_name("nvdsosd0")

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_message)

    osdsinkpad = nvdsosd.get_static_pad("sink")
    if not osdsinkpad:
        sys.stderr.write(" Unable to get sink pad of nvosd \n")

    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)


    pipeline.set_state(Gst.State.PLAYING)

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

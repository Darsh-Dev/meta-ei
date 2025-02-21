#!/usr/bin/python3

# USAGE
# python3 real_time_object_detection.py -v "/dev/video4"

# Details
# This model detect ["aeroplane", "bicycle", "bus", "car", "cat", "cow", "dog", "horse", "motorbike", "person",
#                  "sheep", "train"]

# import the necessary packages
from imutils.video import VideoStream
from imutils.video import FPS
import multiprocessing
import numpy as np
import argparse
import imutils
import time
import cv2
import sys
import os


def detect_objects(inputQueues, outputQueues):
    model = 'pre-trained_model/MobileNetSSD_deploy.caffemodel'
    prototxt = 'pre-trained_model/MobileNetSSD_deploy.prototxt'

    # load our serialized model from disk
    print("Loading trained model...")
    net = cv2.dnn.readNetFromCaffe(prototxt, model)

    # keep looping infinitely until the process is stopped
    while True:
        # if input queue have new frame then do object detection on that frame
        if not inputQueues.empty():
            in_frame = inputQueues.get()

            # convert input frame to a blob
            blob = cv2.dnn.blobFromImage(cv2.resize(in_frame, (300, 300)),
                                         0.007843, (300, 300), 127.5)

            # pass the blob through the network and obtain the detections and
            # predictions
            net.setInput(blob)
            detection = net.forward()

            outputQueues.put(detection)
        else:
            # if input queue is empty then wait for few milisec and try again
            time.sleep(0.005)


# construct the argument parse and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-v", "--videosrc", required=True, default=0,
                help="video device node entry (for usb web camera) or gstreamer pipeline (for mazzanine camera)")
ap.add_argument("-c", "--confidence", type=float, default=0.2,
                help="minimum probability to filter weak detections")
args = vars(ap.parse_args())

MIN_CONF = args["confidence"]

stop_process = False

# initialize our list of queues --
# input Queue contains one frame that need to be process
# output Queue contains detections of latest given input frame
inputQueues = multiprocessing.Queue(maxsize=1)
outputQueues = multiprocessing.Queue(maxsize=1)

# initialize the list of class labels MobileNet SSD was trained to
# detect, then generate a set of bounding box colors for each class
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]

VALID_CLASSES = ["aeroplane", "bicycle", "bus", "car", "cat", "cow", "dog", "horse", "motorbike", "person",
                 "pottedplant", "sheep", "train"]

COLORS = np.random.uniform(0, 255, size=(len(CLASSES), 3))

# initialize the video stream, allow the cammera sensor to warmup,
# and initialize the FPS counter
print("Starting video stream...")

camera_source = int(args["videosrc"]) if len(args["videosrc"]) == 1 else str(args["videosrc"])

vs = VideoStream(src=camera_source).start()
time.sleep(2.0)

# read the first frame and give it to object detection process.
frame = vs.read()

# if we are unable to get video view, exit from program.
if frame is None:
    print("Unable to get video frame. Please check video source.")
    vs.stop()
    sys.exit()

frame = imutils.resize(frame, width=640)

inputQueues.put(frame)

print("Initialized object detection process as daemon...")
od_process = multiprocessing.Process(target=detect_objects, args=(inputQueues, outputQueues))
od_process.daemon = True
od_process.start()


fps = FPS().start()

# initialized detection variable.
detections = []

# loop over the frames from the video stream
while True:
    # grab the frame from the threaded video stream and resize it
    # to have a maximum width of 400 pixels
    frame = vs.read()
    frame = imutils.resize(frame, width=640)

    if inputQueues.empty():
        inputQueues.put(frame)

    # grab the frame dimensions
    (h, w) = frame.shape[:2]

    if not outputQueues.empty():
        detections = outputQueues.get()

    if len(detections):
        # loop over the detections
        for i in np.arange(0, detections.shape[2]):
            # extract the confidence (i.e., probability) associated with
            # the prediction
            confidence = detections[0, 0, i, 2]

            # filter out weak detections by ensuring the `confidence` is
            # greater than the minimum confidence
            if confidence > args["confidence"]:
                # extract the index of the class label from the
                # `detections`, then compute the (x, y)-coordinates of
                # the bounding box for the object
                idx = int(detections[0, 0, i, 1])

                if any(x == CLASSES[idx] for x in VALID_CLASSES):
                    # if classes match then only we will display box.
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")

                    # draw the prediction on the frame
                    label = "{}: {:.2f}%".format(CLASSES[idx],
                                                 confidence * 100)
                    cv2.rectangle(frame, (startX, startY), (endX, endY),
                                  COLORS[idx], 2)
                    y = startY - 15 if startY - 15 > 15 else startY + 15
                    cv2.putText(frame, label, (startX, y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS[idx], 2)

    # show the output frame
    cv2.imshow("Object Detection Demo", frame)
    key = cv2.waitKey(1) & 0xFF

    # if the `q` key was pressed, break from the loop
    if key == ord("q"):
        break

    # update the FPS counter
    fps.update()


# stop the timer and display FPS information
fps.stop()
print("Total Elapsed time: {:.2f}".format(fps.elapsed()))
print("Approx. FPS: {:.2f}".format(fps.fps()))

# do a bit of cleanup
od_process.join(timeout=1.0)
od_process.terminate()

cv2.destroyAllWindows()
cv2.waitKey(1)
vs.stop()
os._exit(0)
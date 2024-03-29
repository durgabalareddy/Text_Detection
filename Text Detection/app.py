import pyrebase
import os
import cv2 as cv
import math
import argparse
from flask import Flask, render_template, request

config = {
    "apiKey": "AIzaSyBb8KSbG9AyRr-6pylR33musgjrySwny-Y",
    "authDomain": "textdetection-ff93a.firebaseapp.com",
    "databaseURL": "https://textdetection-ff93a.firebaseio.com",
    "projectId": "textdetection-ff93a",
    "storageBucket": "textdetection-ff93a.appspot.com",
    "messagingSenderId": "1088715772385",
    "appId": "1:1088715772385:web:7ec709c16c0afeac5dc2a0"
    }

firebase = pyrebase.initialize_app(config)
storage = firebase.storage()



parser = argparse.ArgumentParser(description='Use this script to run text detection deep learning networks using OpenCV.')
# Input argument
parser.add_argument('--input', help='Path to input image or video file. Skip this argument to capture frames from a camera.')
# Model argument
parser.add_argument('--model', default="frozen_east_text_detection.pb",
                    help='Path to a binary .pb file of model contains trained weights.'
                    )
# Width argument
parser.add_argument('--width', type=int, default=320,
                    help='Preprocess input image by resizing to a specific width. It should be multiple by 32.'
                   )
# Height argument
parser.add_argument('--height',type=int, default=320,
                    help='Preprocess input image by resizing to a specific height. It should be multiple by 32.'
                   )
# Confidence threshold
parser.add_argument('--thr',type=float, default=0.5,
                    help='Confidence threshold.'
                   )
# Non-maximum suppression threshold
parser.add_argument('--nms',type=float, default=0.4,
                    help='Non-maximum suppression threshold.'
                   )

args = parser.parse_args()

def decode(scores, geometry, scoreThresh):
    detections = []
    confidences = []

    ############ CHECK DIMENSIONS AND SHAPES OF geometry AND scores ############
    assert len(scores.shape) == 4, "Incorrect dimensions of scores"
    assert len(geometry.shape) == 4, "Incorrect dimensions of geometry"
    assert scores.shape[0] == 1, "Invalid dimensions of scores"
    assert geometry.shape[0] == 1, "Invalid dimensions of geometry"
    assert scores.shape[1] == 1, "Invalid dimensions of scores"
    assert geometry.shape[1] == 5, "Invalid dimensions of geometry"
    assert scores.shape[2] == geometry.shape[2], "Invalid dimensions of scores and geometry"
    assert scores.shape[3] == geometry.shape[3], "Invalid dimensions of scores and geometry"
    height = scores.shape[2]
    width = scores.shape[3]
    for y in range(0, height):

        # Extract data from scores
        scoresData = scores[0][0][y]
        x0_data = geometry[0][0][y]
        x1_data = geometry[0][1][y]
        x2_data = geometry[0][2][y]
        x3_data = geometry[0][3][y]
        anglesData = geometry[0][4][y]
        for x in range(0, width):
            score = scoresData[x]

            # If score is lower than threshold score, move to next x
            if(score < scoreThresh):
                continue

            # Calculate offset
            offsetX = x * 4.0
            offsetY = y * 4.0
            angle = anglesData[x]

            # Calculate cos and sin of angle
            cosA = math.cos(angle)
            sinA = math.sin(angle)
            h = x0_data[x] + x2_data[x]
            w = x1_data[x] + x3_data[x]

            # Calculate offset
            offset = ([offsetX + cosA * x1_data[x] + sinA * x2_data[x], offsetY - sinA * x1_data[x] + cosA * x2_data[x]])

            # Find points for rectangle
            p1 = (-sinA * h + offset[0], -cosA * h + offset[1])
            p3 = (-cosA * w + offset[0],  sinA * w + offset[1])
            center = (0.5*(p1[0]+p3[0]), 0.5*(p1[1]+p3[1]))
            detections.append((center, (w,h), -1*angle * 180.0 / math.pi))
            confidences.append(float(score))

    # Return detections and confidences
    return [detections, confidences]



app = Flask(__name__)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

if not os.path.exists(APP_ROOT+"\static//stop.jpg"):
    storage.child("images/stop.jpg").download(APP_ROOT+"\static//stop.jpg")
if not os.path.exists(APP_ROOT+"\static//kanchipuram.jpg"):
    storage.child("images/kanchipuram.jpg").download(APP_ROOT+"\static//kanchipuram.jpg")
if not os.path.exists(APP_ROOT+"\static//tirujunction.jpg"):
    storage.child("images/tirujunction.jpg").download(APP_ROOT+"\static//tirujunction.jpg")


@app.route("/")
def index():
    return render_template("upload.html",stop_image="stop.jpg",kan_image="kanchipuram.jpg",tir_image="tirujunction.jpg")

@app.route("/upload", methods=['POST'])
def upload():
    target = os.path.join(APP_ROOT, 'static/')
    if not os.path.isdir(target):
            os.mkdir(target)
    if request.form["upload-button"]=="Try It Yourself":
        for file in request.files.getlist("file"):
            filename = file.filename
            destination = "/".join([target, filename])
            storage.child("images/"+filename).put(file)
            file.save(destination)
    else:
        filename = request.form["upload-button"]
        destination = "/".join([target, filename])

    confThreshold = args.thr
    nmsThreshold = args.nms
    inpWidth = args.width
    inpHeight = args.height
    model = args.model

    # Load network
    net = cv.dnn.readNet(model)

    # Create a new named window
    outputLayers = []
    outputLayers.append("feature_fusion/Conv_7/Sigmoid")
    outputLayers.append("feature_fusion/concat_3")


    frame = cv.imread(destination)  
    height_ = frame.shape[0]
    width_ = frame.shape[1]
    rW = width_ / float(inpWidth)
    rH = height_ / float(inpHeight)

        # Create a 4D blob from frame.
    blob = cv.dnn.blobFromImage(frame, 1.0, (inpWidth, inpHeight), (123.68, 116.78, 103.94), True, False)

        # Run the model
    net.setInput(blob)
    output = net.forward(outputLayers)

        # Get scores and geometry
    scores = output[0]
    geometry = output[1]
    [boxes, confidences] = decode(scores, geometry, confThreshold)
        # Apply NMS
    indices = cv.dnn.NMSBoxesRotated(boxes, confidences, confThreshold,nmsThreshold)
    for i in indices:
            # get 4 corners of the rotated rect
        vertices = cv.boxPoints(boxes[i[0]])
            # scale the bounding box coordinates based on the respective ratios
        for j in range(4):
            vertices[j][0] *= rW
            vertices[j][1] *= rH
        for j in range(4):
            p1 = (vertices[j][0], vertices[j][1])
            p2 = (vertices[(j + 1) % 4][0], vertices[(j + 1) % 4][1])
            cv.line(frame, p1, p2, (0, 255, 0), 2, cv.LINE_AA)
    link = storage.child("images/"+filename).get_url(None)
    cv.imwrite(os.path.join(target,"out"+filename),frame)

    return render_template("complete.html", out_image="out"+filename,input_image=filename,l=link)
if __name__ == "__main__":
    app.run(port=8000, debug=True)



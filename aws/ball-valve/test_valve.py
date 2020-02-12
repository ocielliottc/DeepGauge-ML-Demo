# ******************************************************************
#      Author: Dorian Yeager
#        Date: 11/5/2019
# Description: Connect to a remote camera, capture an image and run
#              it through an ML model to determine the state of a
#              ball valve.  0 is closed and 1 is open.
# ******************************************************************

# ******************************************************************
# Import Section
# ******************************************************************

from keras.models import load_model
import cv2, numpy as np

# ******************************************************************
# Class Section
# ******************************************************************

class ValveCamera:
    def __init__(self):
        self.model = load_model("valve-model.h5")

    def checkState(self, uri):
        cap = cv2.VideoCapture(uri)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        ret, frame = cap.read()
        roi = None if (frame is None) else frame[290:790, 710:1210]
        cap.release()

        if (roi is None):
            ## Indicate that the state could not be determined
            move_code = float('nan')
        else:
            img = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, (227, 227))

            pred = self.model.predict(np.array([img]))
            move_code = int(np.argmax(pred[0]))

        return move_code

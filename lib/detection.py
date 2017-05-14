from types import SimpleNamespace as SNS
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import cv2
from lib import np_util as npu
from lib import feature_extraction as fe
from lib.helpers import _x0,_x1,_y0,_y1
# from toolbox.drawer import *


def bbox_coord(top_lf, btm_rt=None):
    btm_rt = btm_rt or top_lf
    return ((top_lf[0][0], top_lf[0][1]), (btm_rt[1][0], btm_rt[1][1]))

def hot_rows_wins(img, window_rows, model, color_space='RGB', min_wd=64,
                spatial_size=(32, 32), hist_bins=32,
                hist_range=(0, 256), orient=9,
                pix_per_cell=8, cell_per_block=2,
                hog_channel=0, spatial_feat=True,
                hist_feat=True, hog_feat=True):
    ''' The "search_windows" function in lesson solution.
    Returns list of hot windows - windows which prediction is possitive for 
    window in windows.
    model: object with .classifier and .X_scaler
    '''
    outrows = []
    img = npu.RGBto(color_space, img)

    # 2) Iterate over all windows in the list
    for row in window_rows:
        hot_wins = []
        bbox = bbox_coord(row[0], row[-1])
        roi = img[_y0(bbox):_y1(bbox), _x0(bbox):_x1(bbox)]
        ht, wd = roi.shape[:2]
        scale = min(ht, wd)/min_wd
        roi = cv2.resize(roi, (int(wd/scale), int(ht/scale)))

        if hog_feat:
            hog_features = fe.hog_features(roi, orient, pix_per_cell, 
                cell_per_block, hog_channel, feature_vec=False)
        for window in row:
            # 3) Extract the test window from original image
            x0 = int(_x0(window)/scale)
            # resized_win_start = int(window[0][0]/scale)
            if wd < x0 + min_wd:
                x0 = wd - min_wd

            test_img = np.array(roi)[:,x0:x0+min_wd]
            # 4) Extract features for that window using single_img_features()
            features = fe.image_features(test_img, color_space=None,
                                         spatial_size=spatial_size, hist_bins=hist_bins,
                                         orient=orient, pix_per_cell=pix_per_cell,
                                         cell_per_block=cell_per_block,
                                         hog_channel=hog_channel, spatial_feat=spatial_feat,
                                         hist_feat=hist_feat, hog_feat=False)
            if hog_feat:
                #print(window,scale,resized_win_start)
                hog_x0 = int(x0/pix_per_cell)
                nblocks = int(min_wd/pix_per_cell) - (cell_per_block-1)
                hog_feature = np.array(hog_features)[:,hog_x0:hog_x0+nblocks].ravel()
                features.append(hog_feature)

            features = np.concatenate(features)
            # 5) Scale extracted features to be fed to classifier
            test_features = model.X_scaler.transform(np.array(features).reshape(1, -1))
            # 6) Predict using your classifier
            prediction = model.classifier.predict(test_features)
            # 7) If positive (prediction == 1) then save the window
            if prediction == 1:
                hot_wins.append(window)
        outrows.append(hot_wins)
    # 8) Return windows for positive detections
    return outrows

class Box():
    def __init__(self, bbox):
        self.x0 = _x0(bbox)
        self.x1 = _x1(bbox)
        self.wd = self.x1 - self.x0

class Car():
    def __init__(self, bbox):
        self.x0 = _x0(bbox)
        self.x1 = _x1(bbox)
        self.wins = [bbox]
        self.boxwd = self.x1 - self.x0

class CarsDetector():
    def __init__(self, model):
        self.img_shape = None
        self.rows = None
        self.cars = []
        self.model = model

    def find_heat_boxes(self, img):
        if self.rows==None:
            self.rows = fe.rows_bboxes(img.shape, dbg=True)
        hot_wins = []
        for hot_row in hot_rows_wins(img, self.rows, self.model, **self.model.defaults):
            heatmap = npu.add_heat(img, bboxes=hot_row)
            hot_wins += fe.heat_bboxes(heatmap, 2)
        return hot_wins

    def detect_cars(self, img):
        new_heats = self.find_heat_boxes(img)
        self.cars = sorted(self.cars, key=lambda car: car.boxwd, reverse=True)

        # this loop won't run on 1st frame as self.cars is empty. 
        # "if new_heats" below will add cars to it if found
        for car in self.cars:
            for i in range(len(new_heats))[::-1]:
                box = Box(new_heats[i])
                # print('car.x0', car.x0, '' <= box.x1 and car.x1 >= box.x0 and car.boxwd*1.5 > box.wd:
                if car.x0 <= box.x1 and car.x1 >= box.x0 and car.boxwd*1.5 > box.wd:
                    car.wins.append(new_heats.pop(i))
        if new_heats:
            cars = []
            for bbox in new_heats:
                heat = Box(bbox)
                found = True
                # cars is [] until it is filled in "if found" below
                for car in cars:
                    if car.x0 <= heat.x1 and car.x1 >= heat.x0:
                        if car.boxwd*2 > heat.wd:
                            car.wins.append(bbox)
                            found = False
                        break
                if found:
                    cars.append(Car(bbox))
            self.cars.extend(cars)

    def draw_detections(self, img):
        # self.detect_cars(img)
        outimg = np.copy(img)
        ghost_cars = []
        for i,car in enumerate(self.cars):
            if car.wins:
                car.wins.pop(0)
            if not car.wins:
                ghost_cars.append(i)

        for ighost in ghost_cars[::-1]:
            self.cars.pop(ighost)

        for i,car in enumerate(self.cars):
            while len(car.wins) > 40:
                car.wins.pop(0)
            if len(car.wins) > 12:
                heatmap = npu.add_heat(img, bboxes=car.wins)
                hot_wins = fe.heat_bboxes(heatmap, 5)
                if hot_wins:
                    heatbox = hot_wins[0]
                if car.boxwd > 20:
                    outimg = cv2.rectangle(outimg, heatbox[0], heatbox[1], (0,255,0), 2)
        return outimg

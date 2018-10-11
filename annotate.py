#!/usr/bin/env python

import tkinter
import tkinter.messagebox
from tkinter import *

from PIL import Image, ImageTk

import os, glob, json

COLORS = [ 'red', 'blue', 'dark green', 'purple', 'dark orange'  ]

class Annotator:
    
    def __init__(self, parent):
        # main frame
        self.parent = parent
        self.parent.title("Captcha Annotator")
        self.frame = Frame(self.parent)
        self.frame.pack(fill=BOTH, expand=1)
        self.parent.resizable(width = False, height = False)

        # initialize state
        self.imageDir = 'data'
        self.imageList = []
        self.scale = 4
        self.state = { 'click': 0, 'x': 0, 'y': 0 }
        self.hline = None
        self.vline = None
        self.bboxId = None
        self.currentImageKey = None
        self.currentImageIndex = None
        self.currentData = None

        # GUI parts - dir entry & load
        self.dirLabel = Label(self.frame, text = "Image Directory:")
        self.dirLabel.grid(row = 0, column = 0, sticky = E)
        self.dirEntry = Entry(self.frame)
        self.dirEntry.insert(END, self.imageDir)
        self.dirEntry.grid(row = 0, column = 1, sticky = W+E)
        self.loadButton = Button(self.frame, text = "Load", command = self.loadDir)
        self.loadButton.grid(row = 0, column = 2, sticky = W+E)

        # GUI parts - text input area
        self.textLabel = Label(self.frame, text = 'Text:')
        self.textLabel.grid(row = 1, column = 0, sticky = E)
        self.textEntry = Entry(self.frame)
        self.textEntry.grid(row = 1, column = 1, sticky = W+E)

        # GUI parts - main panel for annotating
        self.mainPanel = Canvas(self.frame, cursor = 'tcross', width = 350, height = 120)
        self.mainPanel.bind("<Button-1>", self.mouseClick)
        self.mainPanel.bind("<Motion>", self.mouseMove)
        self.parent.bind("<Escape>", self.cancelBBox)  # press <ESCAPE> button to cancel the current bbox
        self.mainPanel.grid(row = 2, column = 0, columnspan = 2, rowspan = 3, sticky = W+N)

        # GUI parts - bboxox info
        self.bboxLabel = Label(self.frame, text = 'Bounding Boxes:')
        self.bboxLabel.grid(row = 1, column = 2, sticky = W+N)
        self.bboxListbox = Listbox(self.frame, width = 22, height = 12)
        self.bboxListbox.grid(row = 2, column = 2, sticky = N)
        self.bboxDeleteButton = Button(self.frame, text = 'Delete', command = self.deleteBBox)
        self.bboxDeleteButton.grid(row = 3, column = 2, sticky = W+E+N)
        self.bboxClearButton = Button(self.frame, text = 'Clear', command = self.clearBBox)
        self.bboxClearButton.grid(row = 4, column = 2, sticky = W+E+N)

        # GUI parts - mouse position
        self.mouse = Label(self.frame, text = '')
        self.mouse.grid(row = 4, column = 0, columnspan = 2, sticky = W+E)
        
        # GUI parts - control panel
        self.controlPanel = Frame(self.frame)
        self.prevButton = Button(self.controlPanel, text='<< Prev', width = 10, command = self.prevImage)
        self.prevButton.pack(side = LEFT, padx = 5, pady = 3)
        self.nextButton = Button(self.controlPanel, text='Next >>', width = 10, command = self.nextImage)
        self.nextButton.pack(side = LEFT, padx = 5, pady = 3)
        self.progLabel = Label(self.controlPanel, text = "Progress: [0000/0000]")
        self.progLabel.pack(side = LEFT, padx = 5)
        self.tmpLabel = Label(self.controlPanel, text = "Go to Image No.")
        self.tmpLabel.pack(side = LEFT, padx = 5)
        self.idxEntry = Entry(self.controlPanel, width = 5)
        self.idxEntry.pack(side = LEFT)
        self.goBtn = Button(self.controlPanel, text = 'Go', command = self.gotoImage)
        self.goBtn.pack(side = LEFT)
        self.saveBtn = Button(self.controlPanel, text = 'Save', command = self.save)
        self.saveBtn.pack(side = RIGHT)
        self.controlPanel.grid(row = 6, column = 0, columnspan = 3, sticky = W+E)

    def loadDir(self):
        newDir = self.dirEntry.get()
        if self.imageDir != newDir:
            self.save()
        self.imageDir = newDir
        self.imageList = glob.glob(os.path.join(self.imageDir, "*.gif"))
        self.imageList.sort()
        if len(self.imageList) == 0:
            print('No *.gif images found in the specified directory.')
            self.dirEntry.delete(0, END)
            self.dirEntry.insert(END, self.imageDir)
            return
        self.datasetFile = os.path.join(self.imageDir, "dataset.json")
        self.dataset = {}
        if os.path.exists(self.datasetFile):
            with open(self.datasetFile, "r") as fp:
                self.dataset = json.load(fp)
            os.rename(self.datasetFile, self.datasetFile + ".orig")
        for i, imageFile in enumerate(self.imageList):
            key = self.imageList[i] = os.path.basename(imageFile)
            if key not in self.dataset:
                self.dataset[key] = { 'text': "", 'bbs': [] }
        self.save()
        self.currentImageIndex = 0
        self.loadImage()

    def loadImage(self):
        self.currentImageKey = self.imageList[self.currentImageIndex]
        self.currentData = self.dataset[self.currentImageKey]

        # load image
        imageFile = os.path.join(self.imageDir, self.currentImageKey)
        self.img = Image.open(imageFile)
        self.img = self.img.resize((self.img.width * self.scale, self.img.height * self.scale))
        self.tkimg = ImageTk.PhotoImage(self.img)
        self.mainPanel.config(width = max(self.tkimg.width(), 350), height = max(self.tkimg.height(), 120))
        self.mainPanel.create_image(0, 0, image = self.tkimg, anchor = NW)

        # set image label
        self.progLabel.config(text = "{} [{:04d}/{:04d}]".format(self.currentImageKey, self.currentImageIndex + 1, len(self.imageList)))
        self.textEntry.delete(0, END)
        self.textEntry.insert(END, self.currentData['text'])

        # bbox list
        self.bboxListbox.delete(0, END)
        self.bboxIdList = []
        for i, bb in enumerate(self.currentData['bbs']):
            self.bboxListbox.insert(END, '({}, {})-({}, {})'.format(bb[0], bb[1], bb[2], bb[3]))
            color = COLORS[i % len(COLORS)]
            self.bboxListbox.itemconfig(i, fg = color)
            rectId = self.drawBBox(bb, color)
            self.bboxIdList.append(rectId)

    def drawBBox(self, bb, color):
        bb = [int(e * self.scale) for e in bb]
        rectId = self.mainPanel.create_rectangle(bb[0], bb[1], bb[2], bb[3], width=2, outline=color)
        return rectId
            
    def save(self):
        if self.datasetFile is None:
            return
        if self.currentImageKey:
            self.currentData['text'] = self.textEntry.get()
            self.currentData['bbs'].sort(key=lambda e: e[0])
            self.dataset[self.currentImageKey] = self.currentData
        with open(self.datasetFile, "w") as fp:
            json.dump(self.dataset, fp, indent = 2)
        
    def mouseClick(self, event):
        if self.state['click'] == 0:
            self.state['x'], self.state['y'] = event.x, event.y
            self.state['click'] = 1
        else:
            bb = [ min(self.state['x'], event.x), min(self.state['y'], event.y),
                   max(self.state['x'], event.x), max(self.state['y'], event.y) ]
            bb = [int(e / self.scale) for e in bb]
            i = len(self.bboxIdList)
            self.bboxListbox.insert(END, '({}, {})-({}, {})'.format(bb[0], bb[1], bb[2], bb[3]))
            color = COLORS[i % len(COLORS)]
            self.bboxListbox.itemconfig(i, fg = color)
            self.currentData['bbs'].append(bb)
            self.bboxIdList.append(self.bboxId)
            self.bboxId = None
            self.state['click'] = 0

    def mouseMove(self, event):
        self.mouse.config(text = '({}, {})'.format(int(event.x / self.scale), int(event.y / self.scale)))
        if self.tkimg:
            if self.hline:
                self.mainPanel.delete(self.hline)
            self.hline = self.mainPanel.create_line(0, event.y, self.tkimg.width(), event.y, width=1, fill='gray')
            if self.vline:
                self.mainPanel.delete(self.vline)
            self.vline = self.mainPanel.create_line(event.x, 0, event.x, self.tkimg.height(), width=1, fill='gray')
        if self.state['click'] == 1:
            if self.bboxId:
                self.mainPanel.delete(self.bboxId)
            bb = [int(e / self.scale) for e in (self.state['x'], self.state['y'], event.x, event.y)]
            color = COLORS[len(self.bboxIdList) % len(COLORS)]
            self.bboxId = self.drawBBox(bb, color)

    def cancelBBox(self, event):
        if self.state['click'] == 1:
            if self.bboxId:
                self.mainPanel.delete(self.bboxId)
                self.bboxId = None
            self.state['click'] = 0

    def nextImage(self, event = None):
        self.save()
        if self.currentImageIndex < len(self.imageList) - 1:
            self.currentImageIndex += 1
            self.loadImage()

    def prevImage(self, event = None):
        self.save()
        if self.currentImageIndex > 0:
            self.currentImageIndex -= 1
            self.loadImage()

    def deleteBBox(self):
        selected = self.bboxListbox.curselection()
        for idx in selected:
            self.mainPanel.delete(self.bboxIdList[idx])
            self.bboxListbox.delete(idx)
            self.bboxIdList.pop(idx)
            self.currentData['bbs'].pop(idx)

    def clearBBox(self):
        for idx in range(len(self.bboxIdList)):
            self.mainPanel.delete(self.bboxIdList[idx])
        self.bboxListbox.delete(0, len(self.bboxIdList))
        self.bboxIdList = []
        self.currentData['bbs'] = []

    def gotoImage(self):
        index = int(self.idxEntry.get()) - 1
        if 0 <= index and index < len(self.imageList):
            self.save()
            self.currentImageIndex = index
            self.loadImage()
    
if __name__ == '__main__':
    root = Tk()
    ann = Annotator(root)
    ann.loadDir()
    root.mainloop()

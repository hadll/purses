import os
try:
    import curses
except:
    from platform import system as currentos
    import subprocess
    import sys
    
    print("Curses not found.")
    if currentos() == "Windows":
        print("You are on windows which has no native curses support.\nWould you like to install a port?")
        while (install_port := input("(y/n)-> ").lower()) not in "yn":
            print("please type y or n")
        if install_port == "n":
            quit()
        elif install_port == "y":
            pyver = sys.version_info[0:2]
            subprocess.run(f"python{pyver[0]}.{pyver[1]} -m pip install windows-curses")
            print("Curses installed.")
    print("Now Closing...")
    quit()

from inspect import getframeinfo, currentframe
from json import load
from colours import Colours
import threading

colours = Colours()

fonts = {}

for font in os.listdir("fonts"):
    with open("fonts/"+font,"r") as f:
        fdict = load(f)
        fonts[fdict["name"]] = fdict

def load_font(path):
    with open(path,"r") as f:
        fdict = load(f)
        fonts[fdict["name"]] = fdict
# this is a sloppy lil function cuz idk if i can use numpy
def tuple_subtract(*tuples:tuple):
    total = tuples[0]
    for tup in tuples[1:]:
        new_total = []
        for i,item in enumerate(tup):
            new_total.append(total[i]-item)
        total = new_total
    return tuple(total)

class Errors:
    def __init__(self) -> None:
        self.log = []
    def __len__(self) -> int:
        return len(self.log)
    def add(self, message):
        frame = currentframe().f_back
        self.log.append(f"ERROR at line [{getframeinfo(frame.f_back).lineno}] when trying to call {getframeinfo(frame).function}: {message}")
    def get(self):
        return self.log
    def dump(self,filename):
        with open(filename,"w") as f:
            f.write("\n".join(self.log))

class Event:
    '''
    ### A class for handling events
    ---
    You can subscribe by using
    - subscribe() -> None

    You can unsubscribe by using
    - unsubscribe() -> None

    You can trigger all subscibers and pass in the args using
    - fire() -> None
    '''
    def __init__(self) -> None:
        self.subscribers = []
    def subscribe(self,func):
        self.subscribers.append(func)
    def unsubscribe(self,func):
        self.subscribers.remove(func)
    def fire(self,*args,**kwargs):
        for func in self.subscribers:
            func(*args,**kwargs)
class Input:
    '''
    ### A class for handling input events
    ---
    You can subscribe to keyboard events using
    - Input.keyboard.subscribe() -> None

    You can subscribe to mouse events using
    - Input.mouse.subscribe() -> None

    You can unsubscribe from keyboard events using
    - Input.keyboard.unsubscribe() -> None

    You can unsubscribe from mouse events using
    - Input.mouse.unsubscribe() -> None
    ---
    #### When a keyboard event is fired, it will pass 
    1) the key code

    #### When a mouse event is fired, it will pass
    1) the position of the mouse as a tuple
    2) the button pressed (1:left, 2:right, or 3:middle)
    3) the event type (down, up) as a string
    '''
    def __init__(self,screen) -> None:
        self.keyboard = Event()
        self.mouse = Event()
        #make a new thread to handle the input
        threading.Thread(target=self.handle,args=(screen,),daemon=True).start()
    def handle(self,screen):
        event = screen.getch()
        if event == curses.KEY_MOUSE:
            _, mx, my, _, minfo = curses.getmouse()
            ##
            ## For some context here, the minfo is an int that is 32 to the power of the button released - 1
            ## so if the left button is released, minfo will be 32^0 = 1
            ##
            ## as for pressed, it is 32 to the power of the button pressed - 1, but it is also multiplied by 2
            ## so if the left button is pressed, minfo will be 32^0 * 2 = 2
            ##
            if minfo in [curses.BUTTON1_PRESSED,curses.BUTTON2_PRESSED,curses.BUTTON3_PRESSED]:
                eventtype = "down"
                minfo/=2 
            elif minfo in [curses.BUTTON1_RELEASED,curses.BUTTON2_RELEASED,curses.BUTTON3_RELEASED]:
                eventtype = "up"
            match minfo:
                case curses.BUTTON1_RELEASED:
                    self.mouse.fire((mx*2,my*2),1,eventtype)
                case curses.BUTTON2_RELEASED:
                    self.mouse.fire((mx*2,my*2),2,eventtype)
                case curses.BUTTON3_RELEASED:
                    self.mouse.fire((mx*2,my*2),3,eventtype)
        else:
            self.keyboard.fire(event)
        self.handle(screen)

class Grid:
    '''
        ### A type for storing data in a 2d grid
        ---
        You can access it using
        - Grid.get() -> any

        And you can write to it using
        - Grid.set() -> any

        You can get if a value is in the grid using
        - Grid.val_exists() -> bool

        You can get if a position is in the range of the grid using
        - Grid.pos_exists() -> bool

        You can get the dimensions of the grid using
        - Grid.get_size() -> tuple (int, int)

    '''
    def __init__(self,w:int,h:int,default="",data:list=[]):
        self.raw = [[default for i in range(h)] for i in range(w)]
        self.w = w
        self.h = h
    def get(self,x:int,y:int):
        '''
        ### Arguments
        #### x:int
        - the x position in the grid to get
        #### y:int
        - the y position in the grid to get
        Gets the data stored at a position in the grid
        '''
        if self.pos_exists(x,y):
            return self.raw[x][y]
        return "0000"
    def set(self,val,x:int,y:int):
        if self.pos_exists(x,y):
            self.raw[x][y]=val
            return val
        else:
            return False
        return "0000"
    def pos_exists(self,x:int,y:int):
        return x<self.w and y<self.h and x>=0 and y >=0
    def val_exists(self,val):
        for x in self.raw:
            for y in x:
                if y == val:
                    return True
        return False
    def get_size(self):
        return (len(self.raw),len(self.raw[0]))
class Screen:
    '''
    ### Arguments
    #### Size:Tuple
    - Size by default is (-1,-1) which automatically matches the size to the terminal.

    ---

    The class which contols the display.

    Things can be drawn to the screen using methods with a "draw" prefix.
    Draw methods push their changes to a buffer.

    To dump this buffer use the method "refresh".
    '''
    def __init__(self,size:tuple=(-1,-1)):
        f = open("charmap.json", encoding='utf8')
        self.charmap = load(f)
        f.close()
        self.errors = Errors()
        self.stdscr = curses.initscr()
        if size == (-1,-1):
            size = self.stdscr.getmaxyx()
        self.errors.add(f"size: {size}")
        self.errors.dump("errors.txt")
        self.display_buffer = Grid(*size,default="0000")
        self.update_event = Event()
        self.stdscr.keypad(1)
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0) 
        curses.mousemask(1)
        self.input = Input(self.stdscr)
    def refresh(self): 
        '''
        Displays what is in the buffer to the terminal

        This method does not clear the buffer
        '''
        for xpos,xval in enumerate(self.display_buffer.raw):
            for ypos,yval in enumerate(xval):
                if len(yval) == 4:
                    ## this is pixels
                    char = self.charmap[yval]
                else:
                    char = yval
                self.stdscr.addch(ypos,xpos,char)
        self.stdscr.refresh()
    def draw_pixel(self,x:int,y:int,v:int=1):
        '''
        ### Arguments
        #### x:int
        - the x position of the pixel
        #### y:int
        - the y position of the pixel
        #### v:int
        - either 0 or 1, being black for 0 and white for 1 as the colour of the pixel
        ---
        pushes a pixel to the buffer, pixels are 1/4th the width of a character
        '''
        tx = x//2
        ty = y//2
        tdata = self.display_buffer.get(tx,ty)
        if len(tdata) != 4: # if its not a pixel map
            tdata = "0000" # overwrite it
        tpos = (x%2)+(y%2)*2
        tdata = tdata[:tpos] + str(v) + tdata[tpos+1:]
        if self.display_buffer.set(tdata,tx,ty) == False:
            self.errors.add("pixel out of range")
            return -1
    def draw_char(self, x:int, y:int, char:str):
        '''
        ### Arguments
        #### x:int
        - the x position of the character
        - (x is rounded to the nearest 2 pixels)
        #### y:int
        - the y position of the character
        - (y is rounded to the nearest 2 pixels)
        #### char:str
        - a string of length 1 to put in the buffer
        ---
        ### pushes a character to the buffer, characters take up a 2x2 area
        ---
        Returns -1 if char length is not 1
        '''
        if len(char) == 1:
            self.display_buffer.set(char,x,y)
        else:
            ## Char too long error
            self.errors.add("char length is not 1")
            return -1
    def draw_str(self, x:int, y:int, string:str, overflow:dict={"type":"none"}):
        '''
        draws a string using the terminal font at the given location
        ### Arguments
        #### x:int
        - the x position of the first char in the string
        - rounded to the nearest 2
        #### y:int
        - the y position of the first char in the string
        - rounded to the nearest 2
        #### string:str
        - the string to put in the buffer
        #### overflow:dict
        - type:str
            - "none"
                - just makes the text keep drawing, even when off screen
                - default
            - "box"
                - uses the w and h keys to define a max width and height which the text will fit to
            - "border"
                - fits the text to the border
        - fit:str
            - "truncate"
                - cuts off the text with the suffix appended to the end
            - "wrap"
                - makes the text wrap back around to the starting x position
                - cuts the text off at the bottom of the box / screen
            - "wrap+truncate"
                - makes the text wrap back around to the starting x position
                - truncates the text on the lowest line of the box / screen
        - w:int
            - width for use with the box type
        - h:int
            - height for use with the box type
        - suffix:str
            - the str that gets appended to the end when using truncate fit
            - default is "..."
        '''
        if "suffix" not in overflow:
            suffix = "..."
            suffixlen = 3
        else:
            suffix = overflow["suffix"]
            suffixlen = len(suffix)
        match overflow["type"]:
            case "none":
                for i,char in enumerate(string):
                    self.draw_char(x+i,y,char)
                return 
            case "box":
                w = overflow["w"] 
                h = overflow["h"] 
            case "border":
                w,h = tuple_subtract(self.display_buffer.get_size(),(x,y))
                w-=x
                h-=y
        match overflow["fit"]:
            case "truncate":
                space=w-suffixlen
                for i,char in enumerate(string[:-suffixlen]):
                    self.draw_char(x+i,y,char)
            case "wrap":
                pass
            case "wrap+truncate":
                pass
    def draw_line(self,x1:int,y1:int,x2:int,y2:int,v:int=1):
        '''
        draws a line between 2 points
        ### Arguments
        #### x1:int
         - the first position's x coordinate
        #### y1:int
         - the first position's y coordinate
        #### x2:int
         - the second position's x coordinate
        #### y2:int
         - the second position's y coordinate
        #### v:int
         - either 0 or 1, being black for 0 and white for 1 as the colour of the pixel
        '''
        x_change = x2 - x1
        y_change = y2 - y1
        abs_x = abs(x_change)
        abs_y = abs(y_change)
        dy = 1 if y_change > 0 else -1
        dx = 1 if x_change > 0 else -1
        if abs_x >= abs_y:
            m_new = 2 * abs_y
            slope_error_new = m_new - abs_x
            y = y1
            for x in range(x1, x2+dx, dx):
                self.draw_pixel(x,y,v)
                if slope_error_new >= 0:
                    y = y+dy
                    slope_error_new = slope_error_new - 2 * abs_x
                slope_error_new = slope_error_new + m_new
        else:
            m_new = 2 * abs_x
            slope_error_new = m_new - abs_y
            x = x1
            for y in range(y1, y2+dy, dy):
                self.draw_pixel(x,y,v)
                if slope_error_new >= 0:
                    x = x+dx
                    slope_error_new = slope_error_new - 2 * abs_y
                slope_error_new = slope_error_new + m_new
    def draw_fill(self,v:int=0):
        for x in range(self.display_buffer.w*2):
            for y in range(self.display_buffer.h*2):
                self.draw_pixel(x,y,v)
    def draw_triangle(self,x1:int,y1:int,x2:int,y2:int,x3:int,y3:int,v:int=1,fill:bool=False):
        self.draw_line(x1,y1,x2,y2,v)
        self.draw_line(x2,y2,x3,y3,v)
        self.draw_line(x3,y3,x1,y1,v)
        if not fill:
            return
        ## find the inner point
        x_sorted = sorted([(x1,y1),(x2,y2),(x3,y3)],key=lambda x: x[0])
        
        inverted = (x_sorted[1][1] - x_sorted[2][1] < ((x_sorted[1][0] - x_sorted[2][0])*(x_sorted[0][1]-x_sorted[2][1])/(x_sorted[0][0]-x_sorted[2][0])))

        min_y=min(y1,y2,y3)
        max_y=max(y1,y2,y3)

        for y in range(min_y,max_y+1):
            for x in range(x_sorted[0][0],x_sorted[2][0]+1):

                if (x_sorted[0][0]-x_sorted[2][0])==0 or (y - x_sorted[2][1] > ((x - x_sorted[2][0])*(x_sorted[0][1]-x_sorted[2][1])/(x_sorted[0][0]-x_sorted[2][0])))^inverted:
                    if (x_sorted[1][0]-x_sorted[0][0])==0 or (y - x_sorted[0][1] < ((x - x_sorted[0][0])*(x_sorted[1][1]-x_sorted[0][1])/(x_sorted[1][0]-x_sorted[0][0])))^inverted:
                        if (x_sorted[2][0]-x_sorted[1][0])==0 or (y - x_sorted[1][1] < ((x - x_sorted[1][0])*(x_sorted[2][1]-x_sorted[1][1])/(x_sorted[2][0]-x_sorted[1][0])))^inverted:
                            self.draw_pixel(x,y,v)
    def draw_rect(self,x:int,y:int,w:int,h:int,v:int=1,fill:bool=False):
        self.draw_line(x,y,x+w,y,v)
        self.draw_line(x+w,y,x+w,y+h,v)
        self.draw_line(x+w,y+h,x,y+h,v)
        self.draw_line(x,y+h,x,y,v)
        if fill:
            for xmod in range(1,w-1):
                for ymod in range(1,h-1):
                    self.draw_pixel(x+xmod,y+xmod,v+xmod)
    def draw_polygon(self, points, v:int=1, fill:bool=False):
        down = len(points) - 1
        up = 0
        for i in range(len(points)-2):
            if i%2 == 0: # even
                self.draw_triangle(points[up][0],points[up][1],points[up+1][0],points[up+1][1],points[down][0],points[down][1],v,fill)
                up+=1
            else:
                self.draw_triangle(points[down][0],points[down][1],points[down-1][0],points[down-1][1],points[up][0],points[up][1],v,fill)
                down-=1
    def draw_str_font(self,x:int,y:int,text:str,font_name:str):
        font_using = fonts[font_name]
        match font_using["case"]:
            case "lower":
                text = text.lower()
            case "upper":
                text = text.upper()
        letter_size = (font_using["char_width"]+font_using["char_spacing"])
        for letternum, letter in enumerate(text):
            if letter == " ":
                continue
            elif letter not in font_using["chars"].keys():
                ## Unknown Char
                letter_bitmap = font_using["chars"]["unknown"]
            else:
                letter_bitmap = font_using["chars"][letter]
            lettermod = letternum*letter_size
            for ymod,row in enumerate(letter_bitmap):
                for xmod,value in enumerate(row):
                    self.draw_pixel(x+xmod+lettermod, y+ymod, value)

#       ui.py
#
#       Copyright 2010 Thomas Jost <thomas.jost@gmail.com>
#
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.

"""
:mod:`pympress.ui` -- GUI management
------------------------------------

This module contains the whole graphical user interface of pympress, which is
made of two separate windows: the Content window, which displays only the
current page in full size, and the Presenter window, which displays both the
current and the next page, as well as a time counter and a clock.

Both windows are managed by the :class:`~pympress.ui.UI` class.
"""
print "in ui.py"
import os
import sys
import time
print "import os,sys, time done"

import pkg_resources
print "import pkg_resources done"

import gi
gi.require_version('Gtk', '3.0')
print "import gi done"
from gi.repository import GObject, Gtk, Pango, Gdk, GdkPixbuf
print "import gobject, gtk, pango, gdk done"

import pympress.pixbufcache
print "import pixbufcache done"
import pympress.util
print "import util done"


import wave

try:
    import pyaudio
    sound_supported=True
except ImportError:
    print 'No sound support. Please, install pyglet module to have one'
    sound_supported=False
PAudio=pyaudio.PyAudio()

def pyaudio_play(snd,chunk=1024):
    stream=PAudio.open(format=PAudio.get_format_from_width(snd.getsampwidth()),
                  channels=snd.getnchannels(),
                  rate=snd.getframerate(),
                  output=True)
    data=snd.readframes(chunk)
    while data!='':
        stream.write(data)
        data=snd.readframes(chunk)



#: "Regular" PDF file (without notes)
PDF_REGULAR      = 0
#: Content page (left side) of a PDF file with notes
PDF_CONTENT_PAGE = 1
#: Notes page (right side) of a PDF file with notes
PDF_NOTES_PAGE   = 2

class UI:
    """Pympress GUI management."""

    #: :class:`~pympress.pixbufcache.PixbufCache` instance.
    cache = None

    #: Content window, as a :class:`Gtk.Window` instance.
    c_win = Gtk.Window(Gtk.WindowType.TOPLEVEL)
    #: :class:`~Gtk.AspectFrame` for the Content window.
    c_frame = Gtk.AspectFrame(ratio=4./3., obey_child=False)
    #: :class:`~Gtk.DrawingArea` for the Content window.
    c_da = Gtk.DrawingArea()

    #: :class:`~Gtk.AspectFrame` for the current slide in the Presenter window.
    p_frame_cur = Gtk.AspectFrame(yalign=1, ratio=4./3., obey_child=False)
    #: :class:`~Gtk.DrawingArea` for the current slide in the Presenter window.
    p_da_cur = Gtk.DrawingArea()
    #: Slide counter :class:`~Gtk.Label` for the current slide.
    label_cur = Gtk.Label()
    #: :class:`~Gtk.EventBox` associated with the slide counter label in the Presenter window.
    eb_cur = Gtk.EventBox()
    #: :class:`~Gtk.Entry` used to switch to another slide by typing its number.
    entry_cur = Gtk.Entry()

    #: :class:`~Gtk.AspectFrame` for the next slide in the Presenter window.
    p_frame_next = Gtk.AspectFrame(yalign=1, ratio=4./3., obey_child=False)
    #: :class:`~Gtk.DrawingArea` for the next slide in the Presenter window.
    p_da_next = Gtk.DrawingArea()
    #: Slide counter :class:`~Gtk.Label` for the next slide.
    label_next = Gtk.Label()

    #: Elapsed time :class:`~Gtk.Label`.
    label_time = Gtk.Label()
    #: Clock :class:`~Gtk.Label`.
    label_clock = Gtk.Label()

    #: Time at which the counter was started.
    start_time = 0
    #: Time elapsed since the beginning of the presentation.
    delta = 0
    #: Timer paused status.
    paused = True

    #: Fullscreen toggle. By default, don't start in fullscreen mode.
    fullscreen = False

    #: Current :class:`~pympress.document.Document` instance.
    doc = None

    #: Whether to use notes mode or not
    notes_mode = False

    #: To remember digital key
    s_go_page_num = ""
    old_event_time = (-sys.maxint)
    
        
    #: Seconds per slide
    seconds_per_slide = 15
    
    #: Slide start time
    start_time_slide = 0
    
    #: Slide elapsed time
    delta_slide = 0
    
    #: Minutes per presentation
    minutes_per_presentation=30
    
    #: We are counting time per with reference to the slide start/end
    # the options are:
    # - 'slide'
    # - 'presentation'
    time_reference='Presentation timing'
    
    #: Whether the time count is forward or reverse
    time_reverse=False

    def __init__(self, doc):
        """
        :param doc: the current document
        :type  doc: :class:`pympress.document.Document`
        """
        black = Gdk.Color(0, 0, 0)

        # Common to both windows
        icon_list = pympress.util.load_icons()

        # Pixbuf cache
        self.cache = pympress.pixbufcache.PixbufCache(doc)

        # Use notes mode by default if the document has notes
        self.notes_mode = doc.has_notes()

        # Content window
        self.c_win.set_title("pympress content")
        self.c_win.set_default_size(800, 600)
        self.c_win.modify_bg(Gtk.StateType.NORMAL, black)
        self.c_win.connect("delete-event", Gtk.main_quit)
        self.c_win.set_icon_list(icon_list)

        self.c_frame.modify_bg(Gtk.StateType.NORMAL, black)

        self.c_da.modify_bg(Gtk.StateType.NORMAL, black)
        self.c_da.connect("draw", self.on_expose)
        self.c_da.set_name("c_da")
        if self.notes_mode:
            self.cache.add_widget("c_da", pympress.document.PDF_CONTENT_PAGE)
        else:
            self.cache.add_widget("c_da", pympress.document.PDF_REGULAR)
        self.c_da.connect("configure-event", self.on_configure)

        self.c_frame.add(self.c_da)
        self.c_win.add(self.c_frame)

        self.c_win.add_events(Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.SCROLL_MASK)
        self.c_win.connect("key-press-event", self.on_key_press)
        self.c_win.connect("scroll-event", self.on_scroll)

        # Presenter window
        p_win = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        p_win.set_title("pympress presenter")
        p_win.set_default_size(800, 600)
        p_win.set_position(Gtk.WindowPosition.CENTER)
        p_win.connect("delete-event", Gtk.main_quit)
        p_win.set_icon_list(icon_list)

        # Put Menu and Table in VBox
        bigvbox = Gtk.VBox(False, 2)
        p_win.add(bigvbox)

        # UI Manager for menu
        ui_manager = Gtk.UIManager()

        # UI description
        ui_desc = '''
        <menubar name="MenuBar">
          <menu action="File">
            <menuitem action="Quit"/>
          </menu>
          <menu action="Presentation">
            <menuitem action="Pause timer"/>
            <menuitem action="Reset timer"/>
            <menuitem action="Fullscreen"/>
            <menuitem action="Notes mode"/>
          </menu>
          <menu action="Timing reference">
            <menuitem action="Presentation timing"/>
            <menuitem action="Slide timing"/>
            <menuitem action="Reverse timing"/>
        <menuitem action="Timing settings"/>
          </menu>

          <menu action="Help">
            <menuitem action="About"/>
          </menu>
        </menubar>'''
        ui_manager.add_ui_from_string(ui_desc)

        # Accelerator group
        accel_group = ui_manager.get_accel_group()
        p_win.add_accel_group(accel_group)

        # Action group
        action_group = Gtk.ActionGroup("MenuBar")
        # Name, stock id, label, accelerator, tooltip, action [, is_active]
        action_group.add_actions([
            ("File",         None,           "_File"),
            ("Presentation", None,           "_Presentation"),
            ("Help",         None,           "_Help"),

            ("Quit",         Gtk.STOCK_QUIT, "_Quit",        "q",  None, Gtk.main_quit),
            ("Reset timer",  None,           "_Reset timer", "r",  None, self.reset_timer),
            ("About",        None,           "_About",       None, None, self.menu_about),
        ])
        action_group.add_toggle_actions([
            ("Pause timer",  None,           "_Pause timer", "p",  None, self.switch_pause,      True),
            ("Fullscreen",   None,           "_Fullscreen",  "f",  None, self.switch_fullscreen, False),
            ("Notes mode",   None,           "_Note mode",   "n",  None, self.switch_mode,       self.notes_mode),
            ("Reverse timing",   None,           "Rever_se timing",   "s",  None, self.switch_countdown,       self.time_reverse),
        ("Timing settings",None,    "Timing settings", None,None, self.menu_timing_settings,False),

        ])
        action_group.add_action(Gtk.Action("Timing reference", "_Timing mode",None, None))
        action_group.add_radio_actions([
            ("Presentation timing",None, "Presentation-wise timing mode",None,None,1),
            ("Slide timing",None, "Slide-wise timing mode", None, None,2)
            ]
            ,1,self.on_timing_mode_changed)

        ui_manager.insert_action_group(action_group)

        # Add menu bar to the window
        menubar = ui_manager.get_widget('/MenuBar')
        h = ui_manager.get_widget('/MenuBar/Help')
        h.set_right_justified(True)
        bigvbox.pack_start(menubar, False,True,0)

        # A little space around everything in the window
        align = Gtk.Alignment.new(0.5, 0.5, 1, 1)
        align.set_padding(20, 20, 20, 20)

        # Table
        table = Gtk.Table(2, 10, False)
        table.set_col_spacings(25)
        table.set_row_spacings(25)
        align.add(table)
        bigvbox.pack_end(align, True, True, 0)

        # "Current slide" frame
        #frame = Gtk.Frame("Current slide")
        frame = Gtk.Frame(label="Current notes")
        table.attach(frame, 0, 6, 0, 1)
        align = Gtk.Alignment.new(0.5, 0.5, 1, 1)
        align.set_padding(0, 0, 12, 0)
        frame.add(align)
        vbox = Gtk.VBox()
        align.add(vbox)
        vbox.pack_start(self.p_frame_cur, True, True, 0)
        self.eb_cur.set_visible_window(False)
        self.eb_cur.connect("event", self.on_label_event)
        vbox.pack_start(self.eb_cur, False, False, 10)
        self.p_da_cur.modify_bg(Gtk.StateType.NORMAL, black)
        self.p_da_cur.connect("draw", self.on_expose)
        self.p_da_cur.set_name("p_da_cur")
        if self.notes_mode:
            self.cache.add_widget("p_da_cur", PDF_NOTES_PAGE)
        else :
            self.cache.add_widget("p_da_cur", PDF_REGULAR)
        self.p_da_cur.connect("configure-event", self.on_configure)
        self.p_frame_cur.add(self.p_da_cur)

        # "Current slide" label and entry
        self.label_cur.set_justify(Gtk.Justification.CENTER)
        self.label_cur.set_use_markup(True)
        self.eb_cur.add(self.label_cur)
        self.entry_cur.set_alignment(0.5)
        self.entry_cur.modify_font(Pango.FontDescription('36'))

        # "Next slide" frame
        #frame = Gtk.Frame("Next slide")
        frame = Gtk.Frame(label="Current slide")
        table.attach(frame, 6, 10, 0, 1)
        align = Gtk.Alignment.new(0.5, 0.5, 1, 1)
        align.set_padding(0, 0, 12, 0)
        frame.add(align)
        vbox = Gtk.VBox()
        align.add(vbox)
        vbox.pack_start(self.p_frame_next, True, True, 0)
        self.label_next.set_justify(Gtk.Justification.CENTER)
        self.label_next.set_use_markup(True)
        vbox.pack_start(self.label_next, False, False, 10)
        self.p_da_next.modify_bg(Gtk.StateType.NORMAL, black)
        self.p_da_next.connect("draw", self.on_expose)
        self.p_da_next.set_name("p_da_next")
        if self.notes_mode:
            self.cache.add_widget("p_da_next", PDF_CONTENT_PAGE)
        else :
            self.cache.add_widget("p_da_next", PDF_REGULAR)
        self.p_da_next.connect("configure-event", self.on_configure)
        self.p_frame_next.add(self.p_da_next)

        # "Time elapsed" frame
        self.elapsed_frame = Gtk.Frame(label="Time elapsed")
        table.attach(self.elapsed_frame, 0, 5, 1, 2, yoptions=Gtk.AttachOptions.FILL)
        align = Gtk.Alignment.new(0.5, 0.5, 1, 1)
        align.set_padding(10, 10, 12, 0)
        self.elapsed_frame.add(align)
        self.label_time.set_justify(Gtk.Justification.CENTER)
        self.label_time.set_use_markup(True)
        align.add(self.label_time)

        # "Clock" frame
        self.clock_frame = Gtk.Frame(label="Clock")
        table.attach(self.clock_frame, 5, 10, 1, 2, yoptions=Gtk.AttachOptions.FILL)
        align = Gtk.Alignment.new(0.5, 0.5, 1, 1)
        align.set_padding(10, 10, 12, 0)
        self.clock_frame.add(align)
        self.label_clock.set_justify(Gtk.Justification.CENTER)
        self.label_clock.set_use_markup(True)
        align.add(self.label_clock)

        p_win.connect("destroy", Gtk.main_quit)
        p_win.show_all()


        # Add events
        p_win.add_events(Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.SCROLL_MASK)
        p_win.connect("key-press-event", self.on_key_press)
        p_win.connect("scroll-event", self.on_scroll)

        # Hyperlinks if available
        if pympress.util.poppler_links_available():
            self.c_da.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
            self.c_da.connect("button-press-event", self.on_button_press)
            self.c_da.connect("motion-notify-event", self.on_motion_notify)

            self.p_da_cur.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
            self.p_da_cur.connect("button-press-event", self.on_button_press)
            self.p_da_cur.connect("motion-notify-event", self.on_motion_notify)

            self.p_da_next.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
            self.p_da_next.connect("button-press-event", self.on_button_press)
            self.p_da_next.connect("motion-notify-event", self.on_motion_notify)

        # Setup timer
        GObject.timeout_add(250, self.update_time)

        # Document
        self.doc = doc
        
        #Setup sound
        #if sound_supported:
        snd_alarm_file=pkg_resources.resource_filename(pkg_resources.Requirement.parse("pympress"),'share/sounds/pympress_alarm.wav')
            #self.snd_alarm=pyglet.media.load(snd_alarm_file,streaming=False)
        self.snd_alarm=wave.open(snd_alarm_file)
    
        

        # Show all windows
        self.c_win.show_all()
        p_win.show_all()


    def run(self):
        """Run the GTK main loop."""
       # with Gdk.lock:
        Gtk.main()


    def menu_about(self, widget=None, event=None):
        """Display the "About pympress" dialog."""
        about = Gtk.AboutDialog()
        about.set_program_name("pympress")
        about.set_version(pympress.__version__)
        about.set_copyright("(c) 2009, 2010 Thomas Jost")
        about.set_comments("pympress is a little PDF reader written in Python using Poppler for PDF rendering and GTK for the GUI.")
        about.set_website("http://www.pympress.org/")
        try:
            req = pkg_resources.Requirement.parse("pympress")
            icon_fn = pkg_resources.resource_filename(req, "share/pixmaps/pympress-128.png")
            about.set_logo(GdkPixbuf.Pixbuf.new_from_file(icon_fn))
        except Exception, e:
            print e
        about.run()
        about.destroy()
    
    def menu_timing_settings(self,widget=None,event=None):
        dlg=Gtk.Dialog("Timing settings")
        dlg.set_default_size(50,100)
        label=Gtk.Label(label="Setup the settings of the timers \ncounting the slide and presentation durations")
        box=dlg.get_content_area()
        box.add(label)
        button_apply=Gtk.Button("Apply")
        button_apply.connect("clicked",self.on_timing_settings_apply)
        
        radio_timing_hbox=Gtk.HButtonBox()
        radio_timing_label=Gtk.Label(label="Timing reference")
        self.radio_timing_presentation=Gtk.RadioButton(None, "Presentation")
        self.radio_timing_slide=Gtk.RadioButton(self.radio_timing_presentation,"Slide")
        if self.time_reference=='Presentation timing':
           self. radio_timing_presentation.set_active(True)
        else:
            self.radio_timing_slide.set_active(True)
        for x in [self.radio_timing_presentation,self.radio_timing_slide]:
            radio_timing_hbox.pack_start(x,False,False,0)
    
        
        radio_tdirection_hbox=Gtk.HButtonBox()
        radio_tdirection_label=Gtk.Label(label="Timing mode")
        self.radio_tdirection_forward=Gtk.RadioButton(None,"Forward")
        self.radio_tdirection_reverse=Gtk.RadioButton(self.radio_tdirection_forward,"Reverse")
        if self.time_reverse:
            self.radio_tdirection_reverse.set_active(True)
        else:
            self.radio_tdirection_forward.set_active(True)
        
        for x in [self.radio_tdirection_forward,self.radio_tdirection_reverse]:
            radio_tdirection_hbox.pack_start(x,False,False,0)
        
        spin_duration_label=Gtk.Label(label="Time limits")
    
        spin_duration_presentation_hbox=Gtk.HButtonBox()
        spin_duration_presentation_label=Gtk.Label(label="minutes per presentation")
        self.presentation_spin=Gtk.SpinButton(Gtk.Adjustment(self.minutes_per_presentation, 1,999,1,1,0),0,0)
        #self.presentation_spin.set_value(self.minutes_per_presentation)
        #print self.presentation_spin.get_value(),'pres spin',self.minutes_per_presentation
        #self.presentation_spin.connect('changed',self.get_spin_value,self.minutes_per_presentation)
        for x in [spin_duration_presentation_label,self.presentation_spin]:
            spin_duration_presentation_hbox.pack_start(x,False,False,0)
    
        spin_duration_slide_hbox=Gtk.HButtonBox()
        spin_duration_slide_label=Gtk.Label(label="seconds per slide")
        self.slide_spin=Gtk.SpinButton(Gtk.Adjustment(self.seconds_per_slide, 1,999,1,1,0),0,0)
        #self.slide_spin.set_value(self.seconds_per_slide)
        self.slide_spin.connect('changed',self.get_spin_value,self.seconds_per_slide)
        for x in [spin_duration_slide_label,self.slide_spin]:
            spin_duration_slide_hbox.pack_start(x,False,False,0)
    
        
        box.add(radio_timing_label)
        box.add(radio_timing_hbox)
        box.add(radio_tdirection_label)
        box.add(radio_tdirection_hbox)
        box.add(spin_duration_label)
        box.add(spin_duration_presentation_hbox)
        box.add(spin_duration_slide_hbox)
        
        box.add(button_apply)
    
        dlg.show_all()
    
    def get_spin_value(widget,spin,value):
        value=spin.get_value_as_int()
    def on_timing_settings_apply(self,widget):
        if self.radio_timing_presentation.get_active():
            self.time_reference='Presentation timing'
        else:
            self.time_reference='Slide timing'
        self.time_reverse=self.radio_tdirection_reverse.get_active()
        self.minutes_per_presentation=self.presentation_spin.get_value_as_int()
        self.seconds_per_slide=self.slide_spin.get_value_as_int()
        print "Timing settings applied"


    def on_page_change(self, unpause=True):
        """
        Switch to another page and display it.

        This is a kind of event which is supposed to be called only from the
        :class:`~pympress.document.Document` class.

        :param unpause: ``True`` if the page change should unpause the timer,
           ``False`` otherwise
        :type  unpause: boolean
        """
        page_cur = self.doc.current_page()
        #page_next = self.doc.next_page()
        page_next = self.doc.current_page()

        # Aspect ratios
        pr = page_cur.get_aspect_ratio(self.notes_mode)
        self.c_frame.set_property("ratio", pr)
        self.p_frame_cur.set_property("ratio", pr)

        if page_next is not None:
            pr = page_next.get_aspect_ratio(self.notes_mode)
            self.p_frame_next.set_property("ratio", pr)

        # Start counter if needed
        if unpause:
            self.paused = False
            if self.start_time == 0:
                self.start_time = time.time()
            self.start_time_slide=time.time()
            
        # If we are counting the time down, reset the time counter
        if self.time_reverse:
            #self.delta=0
            self.delta_slide=0



        # Update display
        self.update_page_numbers()
        
        

        # Don't queue draw event but draw directly (faster)
        self.on_expose(self.c_da)
        self.on_expose(self.p_da_cur)
        self.on_expose(self.p_da_next)

        # Prerender the 4 next pages and the 2 previous ones
        cur = page_cur.number()
        page_max = min(self.doc.pages_number(), cur + 5)
        page_min = max(0, cur - 2)
        for p in range(cur+1, page_max) + range(cur, page_min, -1):
            self.cache.prerender(p)


    def on_expose(self, widget, event=None):
        """
        Manage expose events for both windows.

        This callback may be called either directly on a page change or as an
        event handler by GTK. In both cases, it determines which widget needs to
        be updated, and updates it, using the
        :class:`~pympress.pixbufcache.PixbufCache` if possible.

        :param widget: the widget to update
        :type  widget: :class:`Gtk.Widget`
        :param event: the GTK event (or ``None`` if called directly)
        :type  event: :class:`Gdk.Event`
        
        """

        if widget in [self.c_da, self.p_da_cur]:
            # Current page
            page = self.doc.current_page()
        else:
            # Next page: it can be None
            #page = self.doc.next_page()
            page = self.doc.current_page()
            if page is None:
                widget.hide_all()
                #widget.parent.set_shadow_type(Gtk.ShadowType.NONE)
                return
            else:
                widget.show_all()
                #widget.parent.set_shadow_type(Gtk.ShadowType.IN)

        # Instead of rendering the document to a Cairo surface (which is slow),
        # use a pixbuf from the cache if possible.
        name = widget.get_name()
        nb = page.number()
        pb = self.cache.get(name, nb)
        wtype = self.cache.get_widget_type(name)

        if pb is None:
            # Cache miss: render the page, and save it to the cache
            self.render_page(page, widget, wtype)
            wx,wy,ww,wh=widget.window.get_geometry()
            
            
            #Old (PyGTK2):
            pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, ww, wh)
            #pb.get_from_drawable(widget.window, widget.window.get_colormap(), 0, 0, 0, 0, ww, wh)
            #New (PyGTK3):
            offscreen_window=Gtk.OffscreenWindow()
            offscreen_window.add(widget)
            pb=offscreen_window.get_pixbuf()
                        
            self.cache.set(name, nb, pb)
        else:
            # Cache hit: draw the pixbuf from the cache to the widget
            gc = widget.window.new_gc()
            widget.window.draw_pixbuf(gc, pb, 0, 0, 0, 0)


    def on_configure(self, widget, event):
        """
        Manage "configure" events for both windows.

        In the GTK world, this event is triggered when a widget's configuration
        is modified, for example when its size changes. So, when this event is
        triggered, we tell the local :class:`~pympress.pixbufcache.PixbufCache`
        instance about it, so that it can invalidate its internal cache for the
        specified widget and pre-render next pages at a correct size.

        :param widget: the widget which has been resized
        :type  widget: :class:`Gtk.Widget`
        :param event: the GTK event, which contains the new dimensions of the
           widget
        :type  event: :class:`Gdk.Event`
        """
        self.cache.resize_widget(widget.get_name(), event.width, event.height)


    def on_key_press(self, widget, event):        
        name = Gdk.keyval_name(event.keyval)

        if name in ["Right", "Down", "Page_Down", "space"]:
            self.doc.goto_next()
        elif name in ["Left", "Up", "Page_Up", "BackSpace"]:
            self.doc.goto_prev()
        elif name == 'Home':
            self.doc.goto_home()
        elif name == 'End':
            self.doc.goto_end()
        elif (name.upper() in ["F", "F11"]) \
            or (name == "Return" and event.get_state() & Gdk.ModifierType.MOD1_MASK) \
            or (name.upper() == "L" and event.get_state() & Gdk.ModifierType.CONTROL_MASK):
            self.switch_fullscreen()
        elif name.upper() == "Q":
            Gtk.main_quit()
        elif name == "Pause":
            self.switch_pause()
        elif name.upper() == "R":
            self.reset_timer()
        elif name.upper() == "N":
            self.switch_mode()
        elif name.upper() == "G":
            self.select_page(widget, event, True)
        elif event.string.isdigit():
            self.select_page(widget, event)

        # Some key events are already handled by toggle actions in the
        # presenter window, so we must handle them in the content window
        # only to prevent them from double-firing
        elif widget is self.c_win:
            if name.upper() == "P":
                self.switch_pause()
            elif name.upper() == "N":
                self.switch_mode()


    def on_scroll(self, widget, event):
        if event.direction in [Gdk.ScrollDirection.RIGHT, Gdk.ScrollDirection.DOWN]:
            self.doc.goto_next()
        else:
            self.doc.goto_prev()




    def on_button_press(self, widget, event):
        # Where did the event occur?
        if widget is self.p_da_next:
            #page = self.doc.next_page()
            page = self.doc.current_page()
            if page is None:
                return
        else:
            page = self.doc.current_page()

        # Normalize event coordinates and get link
        x, y = event.get_coords()
        wx,wy,ww, wh = widget.window.get_geometry()
        x2, y2 = x/ww, y/wh
        link = page.get_link_at(x2, y2)

   
        if link is not None:
            dest = link.get_destination()
            self.doc.goto(dest)

    def on_motion_notify(self, widget, event):
        # Where did the event occur?
        if widget is self.p_da_next:
            #page = self.doc.next_page()
            page = self.doc.current_page()
            if page is None:
                return
        else:
            page = self.doc.current_page()
        # Normalize event coordinates and get link
        x, y = event.get_coords()
        wx,wy,ww, wh = widget.window.get_geometry()
        x2, y2 = x/ww, y/wh
        link = page.get_link_at(x2, y2)
        if link is not None:
            cursor = Gdk.Cursor.new(Gdk.HAND2)
            widget.window.set_cursor(cursor)
        else:
            widget.window.set_cursor(None)


    def on_label_event(self, widget, event):
        """
        Manage events on the current slide label/entry.

        This function replaces the label with an entry when clicked, replaces
        the entry with a label when needed, etc. The nasty stuff it does is an
        ancient kind of dark magic that should be avoided as much as possible...

        :param widget: the widget in which the event occured
        :type  widget: :class:`Gtk.Widget`
        :param event: the event that occured
        :type  event: :class:`Gdk.Event`
        """

        widget = self.eb_cur.get_child()

        # Click on the label
        if widget is self.label_cur and event.type == Gdk.EventType.BUTTON_PRESS:
            # Set entry text
            self.entry_cur.set_text("%d/%d" % (self.doc.current_page().number()+1, self.doc.pages_number()))
            self.entry_cur.select_region(0, -1)

            # Replace label with entry
            self.eb_cur.remove(self.label_cur)
            self.eb_cur.add(self.entry_cur)
            self.entry_cur.show()
            self.entry_cur.grab_focus()

        # Key pressed in the entry
        elif widget is self.entry_cur and event.type == Gdk.KEY_RELEASE:
            name = Gdk.keyval_name(event.keyval)

            # Return key --> restore label and goto page
            if name == "Return" or name == "KP_Return":
                text = self.entry_cur.get_text()
                self.restore_current_label()

                # Deal with the text
                n = self.doc.current_page().number() + 1
                try:
                    s = text.split('/')[0]
                    n = int(s)
                except ValueError:
                    print "Invalid number: %s" % text

                n -= 1
                if n != self.doc.current_page().number():
                    if n <= 0:
                        n = 0
                    elif n >= self.doc.pages_number():
                        n = self.doc.pages_number() - 1
                    self.doc.goto(n)

            # Escape key --> just restore the label
            elif name == "Escape":
                self.restore_current_label()

        # Propagate the event further
        return False

    def on_timing_mode_changed(self,widget,current):
        """
        Choose the timing mode
        :param widget: the radio widget
        """
        self.time_reference=current.get_name()

    def render_page(self, page, widget, wtype):
        """
        Render a page on a widget.

        This function takes care of properly initializing the widget so that
        everything looks fine in the end. The rendering to a Cairo surface is
        done using the :meth:`pympress.document.Page.render_cairo` method.

        :param page: the page to render
        :type  page: :class:`pympress.document.Page`
        :param widget: the widget on which the page must be rendered
        :type  widget: :class:`Gtk.DrawingArea`
        :param wtype: the type of document to render
        :type  wtype: integer
        """

        # Make sure the widget is initialized
        widget.window=widget.get_window()
        if widget.window is None:
            return

        # Widget size
        wx,wy,ww,wh=widget.window.get_geometry()

        # Manual double buffering (since we use direct drawing instead of
        # calling queue_draw() on the widget)
        #widget.window.begin_paint_rect((0, 0, ww, wh))
        cr = widget.window.cairo_create()
        cr.rectangle(0,0,ww, wh)
        page.render_cairo(cr, ww, wh, wtype)

        # Blit off-screen buffer to screen
        widget.window.end_paint()


    def restore_current_label(self):
        """
        Make sure that the current page number is displayed in a label and not
        in an entry. If it is an entry, then replace it with the label.
        """
        child = self.eb_cur.get_child()
        if child is not self.label_cur:
            self.eb_cur.remove(child)
            self.eb_cur.add(self.label_cur)


    def update_page_numbers(self):
        """Update the displayed page numbers."""

        text = "<span font='36'>%s</span>"

        cur_nb = self.doc.current_page().number()
        cur = "%d/%d" % (cur_nb+1, self.doc.pages_number())
        next = "--"
        if cur_nb+2 <= self.doc.pages_number():
            #next = "%d/%d" % (cur_nb+2, self.doc.pages_number())
            next = "%d/%d" % (cur_nb+1, self.doc.pages_number())

        self.label_cur.set_markup(text % cur)
        self.label_next.set_markup(text % next)
        self.restore_current_label()


    def update_time(self):
        """
        Update the timer and clock labels.

        :return: ``True`` (to prevent the timer from stopping)
        :rtype: boolean
        """

        text = "<span font='36'>%s</span>"
        red_text=  "<span foreground='red' font='36'>%s</span>"


        # Current time
        clock = time.strftime("%H:%M:%S")

        
        if not self.paused:
            # Time elapsed since the beginning of the presentation
            self.delta = time.time() - self.start_time
            # Time elapsed since the last slide navigation event
            self.delta_slide=time.time() - self.start_time_slide

        
        if self.time_reverse:
            if self.delta<self.minutes_per_presentation*60:
                elapsed = "%02d:%02d" % (int((self.minutes_per_presentation*60 - self.delta)/60), int((self.minutes_per_presentation*60-self.delta)%60))
            else:
                elapsed = "-%02d:%02d" % (int(self.delta/60), int(self.delta%60))
            
            if self.delta_slide<self.seconds_per_slide:
                elapsed_slide = "%02d:%02d" % (int((self.seconds_per_slide - self.delta_slide)/60), int((self.seconds_per_slide-self.delta_slide)%60))
            else:
                elapsed_slide = "-%02d:%02d" % (int((self.delta_slide-self.seconds_per_slide)/60), int((self.delta_slide-self.seconds_per_slide)%60))
           
        else:
            elapsed = "%02d:%02d" % (int(self.delta/60), int(self.delta%60))
            elapsed_slide = "%02d:%02d" % (int(self.delta_slide/60), int(self.delta_slide%60))
        if self.paused:
            elapsed += " (pause)"
            elapsed_slide += " (pause)"

        #: If we are counting time per slide, display it
        if self.time_reference=='Slide timing':
            if elapsed_slide[0]=='-':
                self.label_time.set_markup(red_text % elapsed_slide)
            else:
                self.label_time.set_markup(text % elapsed_slide)
            self.label_clock.set_markup(text % elapsed)
        #: By default we display the time relative to the presentation start/end
        else:
            if elapsed[0]=='-':
                self.label_time.set_markup(red_text % elapsed)
            else:
                self.label_time.set_markup(text % elapsed)
            self.label_clock.set_markup(text % clock)
            
        #Play sound
        if (not self.paused)&(int(self.delta_slide)==self.seconds_per_slide):
            #self.snd_alarm.play()
            pyaudio_play(self.snd_alarm)

        return True


    def switch_pause(self, widget=None, event=None):
        """Switch the timer between paused mode and running (normal) mode."""
        if self.paused:
            self.start_time = time.time() - self.delta
            self.start_time_slide=time.time()-self.delta_slide

            self.paused = False
        else:
            self.paused = True
        self.update_time()


    def reset_timer(self, widget=None, event=None):
        """Reset the timer."""
        self.start_time = time.time()
        self.start_time_slide=time.time()
        self.update_time()


    def set_screensaver(self, must_disable):
        """
        Enable or disable the screensaver.

        .. warning:: At the moment, this is only supported on POSIX systems
           where :command:`xdg-screensaver` is installed and working. For now,
           this feature has only been tested on **Linux with xscreensaver**.

        :param must_disable: if ``True``, indicates that the screensaver must be
           disabled; otherwise it will be enabled
        :type  must_disable: boolean
        """
        if os.name == 'posix':
            # On Linux, set screensaver with xdg-screensaver
            # (compatible with xscreensaver, gnome-screensaver and ksaver or whatever)
            cmd = "suspend" if must_disable else "resume"
            status = os.system("xdg-screensaver %s %s" % (cmd, self.c_win.window.xid))
            if status != 0:
                print >>sys.stderr, "Warning: Could not set screensaver status: got status %d" % status

            # Also manage screen blanking via DPMS
            if must_disable:
                # Get current DPMS status
                pipe = os.popen("xset q") # TODO: check if this works on all locales
                dpms_status = "Disabled"
                for line in pipe.readlines():
                    if line.count("DPMS is") > 0:
                        dpms_status = line.split()[-1]
                        break
                pipe.close()

                # Set the new value correctly
                if dpms_status == "Enabled":
                    self.dpms_was_enabled = True
                    status = os.system("xset -dpms")
                    if status != 0:
                        print >>sys.stderr, "Warning: Could not disable DPMS screen blanking: got status %d" % status
                else:
                    self.dpms_was_enabled = False

            elif self.dpms_was_enabled:
                # Re-enable DPMS
                status = os.system("xset +dpms")
                if status != 0:
                    print >>sys.stderr, "Warning: Could not enable DPMS screen blanking: got status %d" % status
        else:
            print >>sys.stderr, "Warning: Unsupported OS: can't enable/disable screensaver"


    def switch_fullscreen(self, widget=None, event=None):
        """
        Switch the Content window to fullscreen (if in normal mode) or to normal
        mode (if fullscreen).

        Screensaver will be disabled when entering fullscreen mode, and enabled
        when leaving fullscreen mode.
        """
        if self.fullscreen:
            self.c_win.unfullscreen()
            self.fullscreen = False
        else:
            self.c_win.fullscreen()
            self.fullscreen = True

        self.set_screensaver(self.fullscreen)


    def switch_mode(self, widget=None, event=None):
        """
        Switch the display mode to "Notes mode" or "Normal mode" (without notes)
        """
        if self.notes_mode:
            self.notes_mode = False
            self.cache.set_widget_type("c_da", PDF_REGULAR)
            self.cache.set_widget_type("p_da_cur", PDF_REGULAR)
            self.cache.set_widget_type("p_da_next", PDF_REGULAR)
        else:
            self.notes_mode = True
            self.cache.set_widget_type("c_da", PDF_CONTENT_PAGE)
            self.cache.set_widget_type("p_da_cur", PDF_NOTES_PAGE)
            self.cache.set_widget_type("p_da_next", PDF_CONTENT_PAGE)

        self.on_page_change(False)

    def  switch_countdown(self,widget=None,event=None):
        """
        Switch the timing to countdown mode
        """
        #if self.time_reverse:
            #self.start_time=0            
        #else:
            #self.start_time=self.seconds_per_slide
        self.time_reverse=not self.time_reverse
        if self.time_reverse:
            if self.time_reference=='Slide timing':
                self.clock_frame.set_label('Remaining presentation time')
                self.elapsed_frame.set_label('Remainig slide time')
            elif self.time_reference=='Presentation timing':
                self.clock_frame.set_label('Clock')
                self.elapsed_frame.set_label('Remaining')                
        else:
            self.clock_frame.set_label('Clock')
            self.elapsed_frame.set_label('Elapsed')
            
            
        self.update_time()


    def select_page(self, widget=None, event=None, go=False):
        """
        Capture continuous digital keys that are pressed within 1000
        milliseconds, and convert the sequence to an integer. Then go to display
        the corresponding slide page.
        """
        if go :
            if self.s_go_page_num.isdigit() :
                self.doc.goto(int(self.s_go_page_num)-1)
            self.s_go_page_num = ""
        else :
            diff = event.time - self.old_event_time
            if diff >= 0 and diff < 1000 :
                self.s_go_page_num += event.string
            else :
                self.s_go_page_num = event.string
        self.old_event_time = event.time
    
    

##
# Local Variables:
# mode: python
# indent-tabs-mode: nil
# py-indent-offset: 4
# fill-column: 80
# end:

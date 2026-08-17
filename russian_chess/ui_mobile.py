from __future__ import annotations

import base64
import threading
from io import BytesIO
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color as GColor, Ellipse, Line, Rectangle
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget

from .ai import SearchEngine
from .animation import StagedTransfer, begin_visual_step, build_visual_steps, finish_visual_step
from .embedded_assets import ASSETS_B64
from .mobile_controller import MobileGameController, PIECE_NAMES
from .model import Color, PieceType, Square, square_name
from .rules import game_result

LIGHT=(.91,.85,.71,1); DARK=(.57,.40,.28,1); BG=(.10,.115,.14,1)
TEXT=(.95,.96,.98,1); MUTED=(.68,.71,.76,1); GREEN=(.23,.76,.41,.78)
RED=(.88,.28,.28,.88); BLUE=(.24,.58,.94,.9); GOLD=(1,.89,.33,1); DISABLED=(.42,.44,.48,.82)
AI_TIME={"easy":.5,"medium":2.0,"hard":5.0}; STEP=.42; PAUSE=.32
_TEXTURES={}


def texture_for(color: Color, kind: PieceType):
    key=f"pieces/{color.value}_{kind.value}.png"
    if key not in _TEXTURES:
        _TEXTURES[key]=CoreImage(BytesIO(base64.b64decode(ASSETS_B64[key])), ext="png").texture
    return _TEXTURES[key]


class Board(Widget):
    def __init__(self, app, **kw):
        super().__init__(**kw); self.app=app; self.controller=app.controller
        self.display_board=None; self.source_state=None; self.moving_id=None; self.moving_xy=None
        self.staged: StagedTransfer|None=None; self.highlights=set()
        self.bind(pos=lambda *_: self.redraw(), size=lambda *_: self.redraw())

    def rect(self, sq: Square):
        side=min(self.width,self.height); cell=side/8; left=self.x+(self.width-side)/2; bottom=self.y+(self.height-side)/2
        f,r=sq; return left+f*cell,bottom+r*cell,cell,cell

    def center(self,sq):
        x,y,w,h=self.rect(sq); return x+w/2,y+h/2

    def touch_square(self,x,y):
        side=min(self.width,self.height); cell=side/8; left=self.x+(self.width-side)/2; bottom=self.y+(self.height-side)/2
        if not(left<=x<left+side and bottom<=y<bottom+side): return None
        return int((x-left)//cell),int((y-bottom)//cell)

    def on_touch_up(self,touch):
        if self.collide_point(*touch.pos) and not self.app.ai_busy:
            sq=self.touch_square(*touch.pos)
            if sq is not None: self.app.root_ui.square_tapped(sq); return True
        return super().on_touch_up(touch)

    def piece(self,p,sq,shift=0,scale=.86):
        x,y,w,h=self.rect(sq); size=min(w,h)*scale
        Rectangle(texture=texture_for(p.color,p.kind),pos=(x+(w-size)/2+shift,y+(h-size)/2),size=(size,size))

    def piece_xy(self,p,xy):
        side=min(self.width,self.height); size=side/8*.86
        Rectangle(texture=texture_for(p.color,p.kind),pos=(xy[0]-size/2,xy[1]-size/2),size=(size,size))

    def redraw(self):
        self.canvas.clear(); c=self.controller
        state=self.source_state or c.state
        board=self.display_board if self.display_board is not None else c.preview_board()[0]
        overlay=None if self.display_board is not None else c.active_overlay()
        links=[] if self.display_board is not None else c.next_links()
        unavailable=set() if self.display_board is not None else c.unavailable_friendly_targets()
        marks={l.to_square:("transfer" if l.target_friendly_piece_id else "capture" if l.captured_piece_id else "move") for l in links}
        with self.canvas:
            for f in range(8):
                for r in range(8):
                    x,y,w,h=self.rect((f,r)); GColor(*(LIGHT if (f+r)%2 else DARK)); Rectangle(pos=(x,y),size=(w,h))
            for sq,k in marks.items():
                x,y,w,h=self.rect(sq)
                if k=="move": GColor(*GREEN); Ellipse(pos=(x+w*.39,y+h*.39),size=(w*.22,h*.22))
                else: GColor(*(RED if k=="capture" else BLUE)); Line(rectangle=(x+3,y+3,w-6,h-6),width=dp(2))
            for sq in unavailable:
                x,y,w,h=self.rect(sq); GColor(*DISABLED); Line(points=(x+w*.25,y+h*.25,x+w*.75,y+h*.75),width=dp(2)); Line(points=(x+w*.75,y+h*.25,x+w*.25,y+h*.75),width=dp(2))
            for sq in self.highlights:
                x,y,w,h=self.rect(sq); GColor(*GOLD); Line(rectangle=(x+2,y+2,w-4,h-4),width=dp(2.2))
            osq=overlay[1] if overlay else None
            for sq,pid in board.items():
                if pid==self.moving_id: continue
                shift=0
                if osq==sq: shift=-self.rect(sq)[2]*.095
                if self.staged and self.staged.square==sq: shift=self.rect(sq)[2]*.095
                self.piece(state.pieces[pid],sq,shift)
            if overlay:
                pid,sq=overlay; self.piece(state.pieces[pid],sq,self.rect(sq)[2]*.095)
            if self.staged: self.piece(state.pieces[self.staged.piece_id],self.staged.square,-self.rect(self.staged.square)[2]*.095)
            if self.moving_id is not None and self.moving_xy: self.piece_xy(state.pieces[self.moving_id],self.moving_xy)
            if c.selected_piece_id is not None and not c.prefix and self.display_board is None:
                p=c.state.pieces[c.selected_piece_id]
                if p.square: x,y,w,h=self.rect(p.square); GColor(*GOLD); Line(rectangle=(x+2,y+2,w-4,h-4),width=dp(2.3))
            side=min(self.width,self.height); cell=side/8; left=self.x+(self.width-side)/2; bottom=self.y+(self.height-side)/2
            GColor(*MUTED)
            for i,ch in enumerate('abcdefgh'):
                lab=CoreLabel(text=ch,font_size=dp(8),color=MUTED); lab.refresh(); Rectangle(texture=lab.texture,pos=(left+i*cell+3,bottom+2),size=lab.texture.size)


class Root(BoxLayout):
    def __init__(self,app,**kw):
        super().__init__(orientation='vertical',spacing=dp(4),padding=dp(6),**kw); self.app=app; self.controller=app.controller
        head=BoxLayout(size_hint_y=None,height=dp(40)); head.add_widget(Label(text='[b]Русские шахматы[/b]',markup=True,color=TEXT,font_size=dp(20))); self.turn=Label(color=MUTED,size_hint_x=.35); head.add_widget(self.turn); self.add_widget(head)
        self.status=Label(color=TEXT,size_hint_y=None,height=dp(38),halign='center'); self.status.bind(size=lambda w,s:setattr(w,'text_size',s)); self.add_widget(self.status)
        anchor=AnchorLayout(size_hint_y=None); self.board=Board(app,size_hint=(None,None)); anchor.add_widget(self.board); self.add_widget(anchor); self.anchor=anchor
        self.bind(width=lambda *_: self.layout_board()); Clock.schedule_once(lambda *_:self.layout_board(),0)
        nav=BoxLayout(size_hint_y=None,height=dp(40),spacing=dp(4)); self.back=self.btn('◀ Назад',self.hist_back); self.pos=Label(color=MUTED); self.forward=self.btn('Вперёд ▶',self.hist_forward); nav.add_widget(self.back); nav.add_widget(self.pos); nav.add_widget(self.forward); self.add_widget(nav)
        row=BoxLayout(size_hint_y=None,height=dp(40),spacing=dp(4)); row.add_widget(self.btn('Отменить цепочку',self.cancel)); self.sound=self.btn('Звук: вкл',self.toggle_sound); row.add_widget(self.sound); self.add_widget(row)
        self.active=Label(color=GOLD,size_hint_y=None,height=dp(26),font_size=dp(12)); self.add_widget(self.active)
        scroll=ScrollView(); self.history=Label(color=TEXT,size_hint_y=None,halign='left',valign='top',font_size=dp(12),padding=(dp(5),dp(5))); self.history.bind(width=lambda w,v:setattr(w,'text_size',(v,None)),texture_size=lambda w,v:setattr(w,'height',max(dp(48),v[1]+dp(8)))); scroll.add_widget(self.history); self.add_widget(scroll)
        bottom=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(4))
        for t,cb in [('Новая',self.new_popup),('Сохранить',self.save),('Загрузить',self.load),('Правила',self.rules)]: bottom.add_widget(self.btn(t,cb))
        self.add_widget(bottom); self.refresh()

    def btn(self,text,cb):
        b=Button(text=text,background_normal='',background_color=(.25,.29,.36,1),color=TEXT,font_size=dp(12)); b.bind(on_release=cb); return b

    def layout_board(self):
        size=min(self.width-dp(12),dp(540)); self.board.size=(size,size); self.anchor.height=size

    def refresh(self):
        c=self.controller; self.status.text=c.status_message; self.turn.text='Ход: '+('Белые' if c.state.side_to_move is Color.WHITE else 'Чёрные'); self.pos.text=f'{c.timeline.index+1}/{len(c.timeline.states)}'
        self.back.disabled=not c.can_review_back or self.app.ai_busy; self.forward.disabled=not c.can_review_forward or self.app.ai_busy
        aid=c.current_active_piece_id()
        if aid is not None and c.selected_piece_id is not None:
            p=c.state.pieces[aid]; loc=c.prefix[-1] if c.prefix else p.square; self.active.text=f'Активна: {PIECE_NAMES[p.kind]} {square_name(loc) if loc else ""}'
        elif c.is_reviewing: self.active.text='Просмотр истории — ходы заблокированы'
        elif self.app.ai_thinking: self.active.text='Компьютер думает…'
        elif self.app.ai_animating: self.active.text='Компьютер показывает ход…'
        else: self.active.text=''
        h=c.state.move_notation_history; self.history.text='История ходов пока пуста' if not h else '\n'.join(f'{i//2+1}.  {h[i]}    {h[i+1] if i+1<len(h) else ""}' for i in range(0,len(h),2))
        self.sound.text='Звук: вкл' if self.app.sound_enabled else 'Звук: выкл'; self.board.redraw(); Clock.schedule_once(lambda *_:self.app.maybe_ai(),.15)

    def square_tapped(self,sq):
        r=self.controller.tap_square(sq)
        if r.kind=='promotion': self.promotion(r.promotion_moves)
        elif r.kind=='committed' and r.move: self.app.play_sound(r.move.is_capture)
        self.refresh()

    def promotion(self,moves):
        box=BoxLayout(orientation='vertical',spacing=dp(6),padding=dp(8)); pop=Popup(title='Превращение',content=box,size_hint=(.94,None),height=dp(180)); row=BoxLayout(spacing=dp(4)); box.add_widget(Label(text='Выберите фигуру',color=TEXT,size_hint_y=None,height=dp(30)))
        for k,n in [(PieceType.QUEEN,'Ферзь'),(PieceType.ROOK,'Ладья'),(PieceType.BISHOP,'Слон'),(PieceType.KNIGHT,'Конь')]: row.add_widget(self.btn(n,lambda _b,kind=k:self.choose_promotion(pop,moves,kind)))
        box.add_widget(row); pop.open()

    def choose_promotion(self,pop,moves,kind):
        m=self.controller.commit_promotion(moves,kind); self.app.play_sound(m.is_capture); pop.dismiss(); self.refresh()
    def hist_back(self,*_):
        if not self.app.ai_busy and self.controller.review_back(): self.refresh()
    def hist_forward(self,*_):
        if not self.app.ai_busy and self.controller.review_forward(): self.refresh()
    def cancel(self,*_):
        if not self.app.ai_busy: self.controller.cancel_chain(); self.controller.status_message='Цепочка отменена'; self.refresh()
    def toggle_sound(self,*_): self.app.sound_enabled=not self.app.sound_enabled; self.refresh()
    def save(self,*_):
        try: self.controller.save(self.app.save_path); self.controller.status_message='Партия сохранена'
        except Exception as e: self.controller.status_message=f'Ошибка сохранения: {e}'
        self.refresh()
    def load(self,*_):
        try: self.controller.load(self.app.save_path)
        except FileNotFoundError: self.controller.status_message='Сохранённой партии пока нет'
        except Exception as e: self.controller.status_message=f'Ошибка загрузки: {e}'
        self.refresh()

    def new_popup(self,*_):
        box=BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(6)); mode=Spinner(text='Против ИИ',values=('Против ИИ','Два игрока'),size_hint_y=None,height=dp(40)); diff=Spinner(text='Средняя',values=('Лёгкая','Средняя','Сильная'),size_hint_y=None,height=dp(40)); box.add_widget(Label(text='Режим',color=TEXT,size_hint_y=None,height=dp(24))); box.add_widget(mode); box.add_widget(Label(text='Сложность ИИ',color=TEXT,size_hint_y=None,height=dp(24))); box.add_widget(diff); pop=Popup(title='Новая партия',content=box,size_hint=(.9,None),height=dp(290)); box.add_widget(self.btn('Начать',lambda *_:self.start_new(pop,mode.text,diff.text))); pop.open()
    def start_new(self,pop,mode,diff):
        self.app.stop_ai(); self.controller.new_game(mode='ai' if mode=='Против ИИ' else 'local',difficulty={'Лёгкая':'easy','Средняя':'medium','Сильная':'hard'}[diff]); pop.dismiss(); self.refresh()
    def rules(self,*_):
        text='[b]Составной ход[/b]\nФерзь, ладья, слон и конь могут передать право хода дружественной фигуре. Пешка может получить право, но не передаёт его. Король в цепочках не участвует. Синий — передача, зелёный — обычный ход, красный — взятие.'; lab=Label(text=text,markup=True,color=TEXT,halign='left',valign='top',padding=dp(10)); lab.bind(size=lambda w,s:setattr(w,'text_size',s)); Popup(title='Изменённые правила',content=lab,size_hint=(.94,.62)).open()


class RussianChessAndroidApp(App):
    title='Русские шахматы'
    def __init__(self,**kw):
        super().__init__(**kw); self.controller=MobileGameController(); self.root_ui=None; self.ai_stop=threading.Event(); self.ai_generation=0; self.ai_thinking=False; self.ai_animating=False; self.sound_enabled=True; self.move_sound=None; self.capture_sound=None; self.steps=[]; self.move=None; self.source=None; self.anim_board=None; self.staged=None; self.index=0; self.event=None
    @property
    def ai_busy(self): return self.ai_thinking or self.ai_animating
    @property
    def save_path(self): return Path(self.user_data_dir)/'quick_save.json'
    def build(self):
        from kivy.core.window import Window
        Window.clearcolor=BG; d=Path(self.user_data_dir)/'sounds'; d.mkdir(parents=True,exist_ok=True)
        for n in ('move.wav','capture.wav'):
            p=d/n
            if not p.exists(): p.write_bytes(base64.b64decode(ASSETS_B64[f'sounds/{n}']))
        self.move_sound=SoundLoader.load(str(d/'move.wav')); self.capture_sound=SoundLoader.load(str(d/'capture.wav'))
        for s in (self.move_sound,self.capture_sound):
            if s: s.volume=.55
        self.root_ui=Root(self); return self.root_ui
    def play_sound(self,capture=False):
        if not self.sound_enabled: return
        s=self.capture_sound if capture else self.move_sound
        try:
            if s: s.stop(); s.play()
        except Exception: pass
    def stop_ai(self):
        self.ai_stop.set(); self.ai_generation+=1; self.ai_thinking=False; self.ai_animating=False
        if self.event: self.event.cancel(); self.event=None
        if self.root_ui:
            b=self.root_ui.board; b.display_board=None; b.source_state=None; b.moving_id=None; b.moving_xy=None; b.staged=None; b.highlights=set(); b.redraw()
    def maybe_ai(self):
        c=self.controller
        if not self.root_ui or self.ai_busy or c.is_reviewing or c.mode!='ai' or c.state.side_to_move is c.human_color or game_result(c.state): return
        self.ai_thinking=True; c.status_message='Компьютер обдумывает полный ход…'; self.root_ui.refresh(); snap=c.state.clone(); self.ai_stop=threading.Event(); self.ai_generation+=1; gen=self.ai_generation
        def work():
            m=SearchEngine().choose_move(snap,time_limit=AI_TIME[c.difficulty],stop_event=self.ai_stop); Clock.schedule_once(lambda *_:self.ai_ready(gen,m),0)
        threading.Thread(target=work,daemon=True).start()
    def ai_ready(self,gen,m):
        if gen!=self.ai_generation or self.ai_stop.is_set(): return
        self.ai_thinking=False
        if m: self.start_animation(m)
        else: self.root_ui.refresh()
    def start_animation(self,m):
        self.ai_animating=True; self.move=m; self.source=self.controller.state.clone(); self.anim_board=dict(self.controller.state.board); self.staged=None; self.steps=build_visual_steps(self.controller.state,m); self.index=0; b=self.root_ui.board; b.display_board=dict(self.anim_board); b.source_state=self.source; b.staged=None; b.moving_id=None; b.moving_xy=None; b.highlights=set(); self.controller.status_message='ИИ показывает ход по этапам…'; self.root_ui.refresh(); Clock.schedule_once(lambda *_:self.begin_step(),PAUSE)
    def begin_step(self):
        if not self.ai_animating or not self.move: return
        if self.index>=len(self.steps): Clock.schedule_once(lambda *_:self.finish_ai(),PAUSE); return
        st=self.steps[self.index]; self.anim_board,self.staged=begin_visual_step(self.anim_board,st,self.staged); b=self.root_ui.board; b.display_board=dict(self.anim_board); b.staged=self.staged; b.moving_id=st.piece_id; b.highlights={st.from_square,st.to_square}; start=b.center(st.from_square); end=b.center(st.to_square); b.moving_xy=start; p=self.source.pieces[st.piece_id]; self.controller.status_message=f'ИИ — этап {self.index+1}/{len(self.steps)}: {PIECE_NAMES[p.kind]} {square_name(st.from_square)} → {square_name(st.to_square)}'; self.root_ui.refresh(); begun=Clock.get_time()
        def tick(_dt):
            if not self.ai_animating: return False
            t=min(1,(Clock.get_time()-begun)/STEP); e=t*t*(3-2*t); b.moving_xy=(start[0]+(end[0]-start[0])*e,start[1]+(end[1]-start[1])*e); b.redraw()
            if t>=1: self.finish_step(st); return False
            return True
        self.event=Clock.schedule_interval(tick,1/60)
    def finish_step(self,st):
        self.anim_board,self.staged=finish_visual_step(self.anim_board,st); b=self.root_ui.board; b.display_board=dict(self.anim_board); b.staged=self.staged; b.moving_id=None; b.moving_xy=None; b.redraw(); self.play_sound(st.captured_piece_id is not None); self.index+=1; Clock.schedule_once(lambda *_:self.begin_step(),PAUSE)
    def finish_ai(self):
        m=self.move; self.ai_animating=False; self.controller.commit_move(m); b=self.root_ui.board; b.display_board=None; b.source_state=None; b.staged=None; b.moving_id=None; b.moving_xy=None; b.highlights=set(); self.move=None; self.steps=[]; self.root_ui.refresh()
    def on_stop(self): self.stop_ai()


def run_mobile(): RussianChessAndroidApp().run()

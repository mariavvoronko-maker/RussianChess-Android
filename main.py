__version__ = "0.1.1"

import traceback


def _run():
    try:
        from russian_chess.ui_mobile import run_mobile
        run_mobile()
    except Exception:
        # Android startup diagnostics: instead of silently closing after the
        # Kivy presplash, show the Python traceback on screen.
        details = traceback.format_exc()
        print(details, flush=True)
        try:
            from kivy.app import App
            from kivy.uix.label import Label
            from kivy.uix.scrollview import ScrollView

            class StartupErrorApp(App):
                title = "Русские шахматы — ошибка запуска"

                def build(self):
                    label = Label(
                        text="Ошибка запуска\n\n" + details[-6000:],
                        size_hint_y=None,
                        halign="left",
                        valign="top",
                        font_size="12sp",
                    )
                    label.bind(
                        width=lambda w, v: setattr(w, "text_size", (v, None)),
                        texture_size=lambda w, v: setattr(w, "height", max(v[1] + 24, 200)),
                    )
                    scroll = ScrollView(do_scroll_x=False)
                    scroll.add_widget(label)
                    return scroll

            StartupErrorApp().run()
        except Exception:
            print(traceback.format_exc(), flush=True)
            raise


if __name__ == "__main__":
    _run()

#!/usr/bin/env python3
"""GTK3 front end for exerunner. Cinnamon ships everything this needs."""

import os
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Gdk, GdkPixbuf  # noqa: E402

core = None  # set by main()


# --------------------------------------------------------------------------
# a window that streams a long-running job's output
# --------------------------------------------------------------------------


class TaskWindow(Gtk.Window):
    def __init__(self, parent, title, work, on_done=None):
        super().__init__(title=title, transient_for=parent, modal=parent is not None)
        self.set_default_size(720, 420)
        self.set_position(
            Gtk.WindowPosition.CENTER_ON_PARENT if parent else Gtk.WindowPosition.CENTER
        )
        self.on_done = on_done
        self.result = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(12)
        self.add(box)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.spinner = Gtk.Spinner()
        self.spinner.start()
        header.pack_start(self.spinner, False, False, 0)
        self.status = Gtk.Label(label="Working...", xalign=0)
        header.pack_start(self.status, True, True, 0)
        box.pack_start(header, False, False, 0)

        self.buffer = Gtk.TextBuffer()
        view = Gtk.TextView(buffer=self.buffer, editable=False, monospace=True)
        view.set_wrap_mode(Gtk.WrapMode.CHAR)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.add(view)
        box.pack_start(scroller, True, True, 0)
        self.view = view

        self.close_button = Gtk.Button(label="Close")
        self.close_button.set_sensitive(False)
        self.close_button.connect("clicked", lambda *_: self.destroy())
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        actions.pack_end(self.close_button, False, False, 0)
        box.pack_start(actions, False, False, 0)

        self.show_all()
        threading.Thread(target=self._run, args=(work,), daemon=True).start()

    def log(self, text):
        def append():
            end = self.buffer.get_end_iter()
            self.buffer.insert(end, text + "\n")
            self.view.scroll_to_mark(self.buffer.get_insert(), 0.0, True, 0.0, 1.0)
            return False

        GLib.idle_add(append)

    def set_status(self, text):
        GLib.idle_add(lambda: (self.status.set_text(text), False)[1])

    def _run(self, work):
        try:
            self.result = work(self)
        except Exception as exc:  # surfaced in the log rather than swallowed
            self.log(f"\n!! {type(exc).__name__}: {exc}")
            self.result = exc

        def finish():
            self.spinner.stop()
            self.status.set_text("Finished.")
            self.close_button.set_sensitive(True)
            if self.on_done:
                self.on_done(self.result)
            return False

        GLib.idle_add(finish)


# --------------------------------------------------------------------------
# install dialog
# --------------------------------------------------------------------------


class InstallDialog(Gtk.Dialog):
    def __init__(self, parent, exe_path=""):
        super().__init__(title="Add a Windows app", transient_for=parent, modal=True)
        self.set_default_size(560, 0)
        # Without a parent to centre on, place it on screen explicitly - it can
        # otherwise open partly off the left edge.
        self.set_position(
            Gtk.WindowPosition.CENTER_ON_PARENT if parent else Gtk.WindowPosition.CENTER
        )
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Install", Gtk.ResponseType.OK).get_style_context().add_class("suggested-action")

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        outer.set_border_width(20)
        self.get_content_area().add(outer)

        # --- headline: the app's own icon and name, nothing technical ------
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.app_image = Gtk.Image()
        self._load_exe_icon(exe_path)
        head.pack_start(self.app_image, False, False, 0)

        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        titles.set_valign(Gtk.Align.CENTER)
        self.headline = Gtk.Label(xalign=0)
        self.headline.set_line_wrap(True)
        self.headline.set_max_width_chars(34)
        titles.pack_start(self.headline, False, False, 0)

        blurb = Gtk.Label(xalign=0)
        blurb.set_markup(
            "<small>Installs into its own private container, so it can't\n"
            "affect anything else on your computer.</small>"
        )
        blurb.get_style_context().add_class("dim-label")
        titles.pack_start(blurb, False, False, 0)
        head.pack_start(titles, True, True, 0)
        outer.pack_start(head, False, False, 0)

        # --- the one thing worth asking about upfront ----------------------
        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        name_label = Gtk.Label(label="Name it", xalign=1)
        name_label.get_style_context().add_class("dim-label")
        name_row.pack_start(name_label, False, False, 0)
        outer.pack_start(name_row, False, False, 0)

        # --- everything technical, folded away -----------------------------
        advanced = Gtk.Expander(label="Advanced options")
        grid = Gtk.Grid(row_spacing=10, column_spacing=12)
        grid.set_margin_top(12)
        grid.set_margin_start(4)
        advanced.add(grid)
        outer.pack_end(advanced, False, False, 0)
        row = 0

        def label(text):
            widget = Gtk.Label(label=text, xalign=1)
            widget.get_style_context().add_class("dim-label")
            return widget

        # file chooser. width_chars pins the request so a long path scrolls
        # inside the entry instead of stretching the whole dialog off-screen.
        self.file_entry = Gtk.Entry(text=exe_path, hexpand=True, width_chars=32, max_width_chars=32)
        self.file_entry.set_tooltip_text(exe_path or "")
        browse = Gtk.Button(label="Browse...")
        browse.connect("clicked", self.on_browse)
        file_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        file_box.pack_start(self.file_entry, True, True, 0)
        file_box.pack_start(browse, False, False, 0)
        grid.attach(label("Windows .exe"), 0, row, 1, 1)
        grid.attach(file_box, 1, row, 1, 1)
        row += 1

        self.name_entry = Gtk.Entry(hexpand=True, width_chars=28, max_width_chars=28)
        if exe_path:
            self.name_entry.set_text(core.name_from_filename(Path(exe_path).stem))
        self.name_entry.connect("changed", self._sync_headline)
        self.file_entry.connect(
            "changed",
            lambda e: self.name_entry.get_text()
            or self.name_entry.set_text(core.name_from_filename(Path(e.get_text()).stem)),
        )
        name_row.pack_start(self.name_entry, True, True, 0)
        self._sync_headline()

        self.kind = Gtk.ComboBoxText()
        self.kind.append("installer", "It is an installer (runs a setup wizard)")
        self.kind.append("portable", "It is portable (runs directly, no install)")
        self.kind.set_active(0)
        grid.attach(label("Type"), 0, row, 1, 1)
        grid.attach(self.kind, 1, row, 1, 1)
        row += 1

        # Plain-language labels; the package list goes in the tooltip so it
        # cannot stretch the dialog.
        PRESET_BLURBS = {
            "app": "Normal software (recommended)",
            "dotnet": "Needs .NET Framework",
            "directx": "Needs DirectX helper libraries",
            "game": "Game (DirectX plus DXVK)",
            "media": "Plays video or audio",
            "full": "Everything (slow, troubleshooting only)",
            "minimal": "Nothing extra",
        }
        self.preset = Gtk.ComboBoxText()
        for key, verbs in sorted(core.PRESETS.items()):
            self.preset.append(key, PRESET_BLURBS.get(key, key))
        self.preset.set_active_id("app")
        self.preset.set_tooltip_text(
            "\n".join(f"{k}: {', '.join(v) if v else 'nothing'}"
                      for k, v in sorted(core.PRESETS.items()))
        )
        grid.attach(label("Runtimes"), 0, row, 1, 1)
        grid.attach(self.preset, 1, row, 1, 1)
        row += 1

        self.runner = Gtk.ComboBoxText()
        for name in core.list_runners():
            self.runner.append(name, name)
        self.runner.set_active_id("system")
        grid.attach(label("Wine build"), 0, row, 1, 1)
        grid.attach(self.runner, 1, row, 1, 1)
        row += 1

        self.arch = Gtk.ComboBoxText()
        self.arch.append("64", "64-bit (default)")
        self.arch.append("32", "32-bit (older apps)")
        self.arch.set_active_id("64")
        grid.attach(label("Architecture"), 0, row, 1, 1)
        grid.attach(self.arch, 1, row, 1, 1)
        row += 1

        self.winver = Gtk.ComboBoxText()
        for value, text in (("win10", "Windows 10"), ("win7", "Windows 7"), ("winxp", "Windows XP")):
            self.winver.append(value, text)
        self.winver.set_active_id("win10")
        grid.attach(label("Reports as"), 0, row, 1, 1)
        grid.attach(self.winver, 1, row, 1, 1)
        row += 1

        self.show_all()
        advanced.set_expanded(False)  # show_all reveals children; keep it folded

    def _sync_headline(self, *_args):
        name = self.name_entry.get_text().strip() or "this program"
        self.headline.set_markup(f"<big><b>{GLib.markup_escape_text(name)}</b></big>")

    def _load_exe_icon(self, exe_path):
        """Show the program's own icon, so it reads as *this app* installing."""
        import shutil as sh
        import tempfile

        pixbuf = None
        if exe_path and Path(exe_path).is_file():
            work = Path(tempfile.mkdtemp(prefix="exerunner-icon-"))
            try:
                extracted = core.extract_icon(Path(exe_path), work / "icon.png")
                if extracted:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(str(extracted), 64, 64)
            except (GLib.Error, OSError):
                pixbuf = None
            finally:
                sh.rmtree(work, ignore_errors=True)

        if pixbuf is None:
            try:
                pixbuf = Gtk.IconTheme.get_default().load_icon("application-x-executable", 64, 0)
            except GLib.Error:
                return
        self.app_image.set_from_pixbuf(pixbuf)

    def on_browse(self, _button):
        chooser = Gtk.FileChooserDialog(
            title="Choose a Windows .exe", transient_for=self, action=Gtk.FileChooserAction.OPEN
        )
        chooser.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Open", Gtk.ResponseType.OK)
        filt = Gtk.FileFilter()
        filt.set_name("Windows programs (*.exe, *.msi)")
        filt.add_pattern("*.exe")
        filt.add_pattern("*.msi")
        chooser.add_filter(filt)
        if chooser.run() == Gtk.ResponseType.OK:
            self.file_entry.set_text(chooser.get_filename())
        chooser.destroy()

    def values(self):
        return {
            "exe": self.file_entry.get_text().strip(),
            "name": self.name_entry.get_text().strip(),
            "portable": self.kind.get_active_id() == "portable",
            "preset": self.preset.get_active_id(),
            "runner": self.runner.get_active_id(),
            "arch": self.arch.get_active_id(),
            "winver": self.winver.get_active_id(),
        }


# --------------------------------------------------------------------------
# main window
# --------------------------------------------------------------------------


class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Windows Apps")
        self.set_default_size(760, 480)
        self.set_position(Gtk.WindowPosition.CENTER)

        header = Gtk.HeaderBar(title="Windows Apps", subtitle="one clean Wine prefix per app", show_close_button=True)
        self.set_titlebar(header)

        add = Gtk.Button()
        add.add(Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON))
        add.set_tooltip_text("Add a Windows app")
        add.connect("clicked", lambda *_: self.open_install_dialog())
        header.pack_start(add)

        doctor = Gtk.Button(label="Check system")
        doctor.set_tooltip_text("Verify Wine and its dependencies are set up correctly")
        doctor.connect("clicked", self.on_doctor)
        header.pack_end(doctor)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(outer)

        # app list
        self.store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str)  # icon, markup, slug, runner
        self.view = Gtk.IconView(model=self.store)
        self.view.set_pixbuf_column(0)
        self.view.set_markup_column(1)
        self.view.set_item_width(140)
        self.view.set_columns(-1)
        self.view.connect("item-activated", self.on_activate)
        self.view.connect("button-press-event", self.on_click)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.view)
        outer.pack_start(scroller, True, True, 0)

        self.empty = Gtk.Label(xalign=0.5, yalign=0.5)
        self.empty.set_markup(
            "<big>No Windows apps yet</big>\n\n"
            "<span alpha='70%'>Click + above, or drag a .exe file onto this window.</span>"
        )
        outer.pack_start(self.empty, True, True, 0)

        self.statusbar = Gtk.Label(xalign=0)
        self.statusbar.get_style_context().add_class("dim-label")
        self.statusbar.set_margin_start(10)
        self.statusbar.set_margin_end(10)
        self.statusbar.set_margin_top(4)
        self.statusbar.set_margin_bottom(6)
        outer.pack_start(self.statusbar, False, False, 0)

        # drag and drop an .exe onto the window
        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.drag_dest_add_uri_targets()
        self.connect("drag-data-received", self.on_drop)

        self.refresh()

    # -- data ------------------------------------------------------------

    def refresh(self):
        self.store.clear()
        theme = Gtk.IconTheme.get_default()
        apps = core.all_apps()
        for app in apps:
            icon_path = core.app_dir(app["slug"]) / "icon.png"
            pixbuf = None
            if icon_path.exists():
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(str(icon_path), 64, 64)
                except GLib.Error:
                    pixbuf = None
            if pixbuf is None:
                try:
                    pixbuf = theme.load_icon("application-x-executable", 64, 0)
                except GLib.Error:
                    pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 64, 64)
            markup = f"{GLib.markup_escape_text(app['name'])}"
            self.store.append([pixbuf, markup, app["slug"], app.get("runner", "system")])

        self.empty.set_visible(not apps)
        self.view.get_parent().set_visible(bool(apps))
        self.statusbar.set_text(
            f"{len(apps)} app(s)   -   prefixes in {core.DATA}" if apps else "Ready."
        )

    def selected_slug(self):
        items = self.view.get_selected_items()
        if not items:
            return None
        return self.store[items[0]][2]

    # -- actions ---------------------------------------------------------

    def open_install_dialog(self, exe_path=""):
        dialog = InstallDialog(self, exe_path)
        response = dialog.run()
        values = dialog.values()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        if not values["exe"] or not Path(values["exe"]).is_file():
            self.error("Pick a .exe file first.")
            return
        self.do_install(values)

    def do_install(self, values):
        def work(task):
            exe = Path(values["exe"]).resolve()
            name = values["name"] or exe.stem
            slug = core.slugify(name)
            target = core.app_dir(slug)
            if target.exists():
                import shutil

                shutil.rmtree(target)
            prefix = target / "prefix"
            log_path = target / "logs" / "install.log"
            arch = "win32" if values["arch"] == "32" else "win64"
            verbs = core.PRESETS.get(values["preset"], [])

            task.set_status("Creating an isolated Wine prefix...")
            task.log(f"Prefix: {prefix}")
            core.create_prefix(prefix, values["runner"], arch, log_path, on_line=task.log)

            if verbs:
                task.set_status(f"Installing runtimes: {', '.join(verbs)} (this can take a while)")
                core.run_winetricks(prefix, values["runner"], verbs, log_path, on_line=task.log)

            task.set_status(f"Setting Windows version to {values['winver']}")
            core.set_winver(prefix, values["runner"], values["winver"], log_path, on_line=task.log)

            import time

            started = time.time()
            env, wine = core.wine_env(prefix, values["runner"])

            if values["portable"]:
                dest_dir = prefix / "drive_c" / "apps" / slug
                dest_dir.mkdir(parents=True, exist_ok=True)
                import shutil as _shutil

                _shutil.copy2(exe, dest_dir / exe.name)
                main_exe = dest_dir / exe.name
            else:
                task.set_status("Running the installer - complete its wizard as usual")
                task.log(f"$ wine {exe}")
                core.stream([wine, str(exe)], env=env, cwd=exe.parent, log_path=log_path, on_line=task.log)
                if not core.wait_idle(env):
                    task.log("The installer handed off to the app, which is still running - carrying on.")
                task.set_status("Looking for the installed program...")
                candidates = core.find_candidates(prefix, since=started)
                if not candidates:
                    task.log("No installed executable found in the prefix.")
                    return None
                main_exe = candidates[0]
                task.log(f"Main executable: {main_exe}")

            manifest = {
                "slug": slug,
                "name": name,
                "exe": str(main_exe),
                "args": [],
                "workdir": str(main_exe.parent),
                "prefix": str(prefix),
                "runner": values["runner"],
                "arch": arch,
                "winver": values["winver"],
                "tricks": verbs,
                "env": {},
                "source": str(exe),
                "created": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            }
            core.save_app(manifest)
            core.extract_icon(main_exe, target / "icon.png", slug=slug)
            core.write_desktop_entry(manifest)
            task.log(f"\nDone. '{name}' is installed and now appears in your menu.")
            return manifest

        TaskWindow(self, "Installing", work, on_done=lambda _r: self.refresh())

    def on_activate(self, _view, path):
        self.launch(self.store[path][2])

    def launch(self, slug):
        manifest = core.load_app(slug)
        env, wine = core.wine_env(manifest["prefix"], manifest.get("runner", "system"), extra=manifest.get("env"))
        log_path = core.app_dir(slug) / "logs" / "last.log"
        if log_path.exists():
            log_path.unlink()

        def work(task):
            task.set_status(f"Running {manifest['name']}")
            return core.stream(
                [wine, manifest["exe"]] + list(manifest.get("args") or []),
                env=env,
                cwd=manifest.get("workdir"),
                log_path=log_path,
                on_line=task.log,
            )

        def done(code):
            self.statusbar.set_text(
                f"{manifest['name']} exited with code {code}" if code else f"{manifest['name']} closed cleanly."
            )

        TaskWindow(self, manifest["name"], work, on_done=done)

    def on_click(self, view, event):
        if event.button != 3:  # right click
            return False
        path = view.get_path_at_pos(int(event.x), int(event.y))
        if not path:
            return False
        view.select_path(path)
        slug = self.store[path][2]
        manifest = core.load_app(slug)

        menu = Gtk.Menu()

        def item(label, handler):
            entry = Gtk.MenuItem(label=label)
            entry.connect("activate", lambda *_: handler())
            menu.append(entry)

        item("Run", lambda: self.launch(slug))
        menu.append(Gtk.SeparatorMenuItem())
        if core.desktop_shortcut_path(manifest).exists():
            item("Remove icon from desktop", lambda: self.desktop_icon(manifest, False))
        else:
            item("Add icon to desktop", lambda: self.desktop_icon(manifest, True))
        menu.append(Gtk.SeparatorMenuItem())
        item("Wine configuration...", lambda: self.prefix_tool(manifest, "winecfg"))
        item("Install more runtimes (winetricks)...", lambda: self.prefix_tool(manifest, "winetricks"))
        item("Registry editor...", lambda: self.prefix_tool(manifest, "regedit"))
        item("Open prefix folder", lambda: self.prefix_tool(manifest, "files"))
        menu.append(Gtk.SeparatorMenuItem())
        item("View last log", lambda: self.show_log(slug))
        item("Force-stop this app", lambda: self.prefix_tool(manifest, "kill"))
        menu.append(Gtk.SeparatorMenuItem())
        item("Remove app and its prefix...", lambda: self.remove(manifest))

        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def desktop_icon(self, manifest, add):
        if add:
            path = core.write_desktop_shortcut(manifest)
            self.statusbar.set_text(f"Desktop icon created: {path}")
        else:
            core.remove_desktop_shortcut(manifest["slug"])
            self.statusbar.set_text(f"Desktop icon removed for {manifest['name']}")

    def prefix_tool(self, manifest, tool):
        import subprocess

        env, wine = core.wine_env(manifest["prefix"], manifest.get("runner", "system"))
        if tool == "files":
            subprocess.Popen(["xdg-open", str(Path(manifest["prefix"]) / "drive_c")])
        elif tool == "winetricks":
            if not core.which("winetricks"):
                self.error("winetricks is not installed.\n\nsudo apt install winetricks")
                return
            subprocess.Popen(["winetricks"], env=env)
        elif tool == "kill":
            subprocess.Popen([env.get("WINESERVER", "wineserver"), "-k"], env=env)
            self.statusbar.set_text(f"Stopped everything in the '{manifest['slug']}' prefix.")
        else:
            subprocess.Popen([wine, tool], env=env)

    def show_log(self, slug):
        path = core.app_dir(slug) / "logs" / "last.log"
        if not path.exists():
            self.error("No log yet - run the app once.")
            return
        text = path.read_text(encoding="utf-8", errors="replace")

        window = Gtk.Window(title=f"Log - {slug}", transient_for=self)
        window.set_default_size(760, 480)
        buffer = Gtk.TextBuffer()
        buffer.set_text(text[-200000:])
        view = Gtk.TextView(buffer=buffer, editable=False, monospace=True)
        view.set_wrap_mode(Gtk.WrapMode.CHAR)
        scroller = Gtk.ScrolledWindow()
        scroller.add(view)
        window.add(scroller)
        window.show_all()

    def remove(self, manifest):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Remove {manifest['name']}?",
        )
        dialog.format_secondary_text(
            "This deletes the app, its Wine prefix and everything saved inside it. It cannot be undone."
        )
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        import shutil

        core.remove_desktop_entry(manifest["slug"])
        shutil.rmtree(core.app_dir(manifest["slug"]), ignore_errors=True)
        self.refresh()

    def on_doctor(self, _button):
        def work(task):
            import io
            import contextlib

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = core.cmd_doctor(None)
            task.log(out.getvalue())
            return code

        TaskWindow(self, "System check", work)

    def on_drop(self, _widget, _ctx, _x, _y, data, _info, _time):
        uris = data.get_uris()
        if not uris:
            return
        path = GLib.filename_from_uri(uris[0])[0]
        if not path.lower().endswith((".exe", ".msi")):
            self.error("Drop a .exe or .msi file.")
            return
        self.open_install_dialog(path)

    def error(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text=message,
        )
        dialog.run()
        dialog.destroy()


class Wizard:
    """The flow you get when you double-click a .exe in the file manager.

    Deliberately has no main window - it is a dialog sequence that appears,
    does the job, and gets out of the way.
    """

    def __init__(self, exe_path):
        self.exe_path = exe_path
        self.result = None

    def run(self):
        exe = Path(self.exe_path)

        if core.REDIST_INSTALLER.search(exe.name):
            dialog = Gtk.MessageDialog(
                modal=True, message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                text="This looks like a Microsoft redistributable installer",
            )
            dialog.format_secondary_text(
                f"{exe.name} installs a Windows runtime by downloading it through "
                "Windows Update, which does not exist on Linux, so it cannot work.\n\n"
                "Wine already provides DirectX. What apps actually need are helper "
                "libraries, which you add to an app with Runtimes in the app's menu.\n\n"
                "Continue anyway?"
            )
            response = dialog.run()
            dialog.destroy()
            if response != Gtk.ResponseType.OK:
                return 1

        dialog = InstallDialog(None, str(exe))
        dialog.set_title("Install a Windows app")
        response = dialog.run()
        values = dialog.values()
        dialog.destroy()

        if response != Gtk.ResponseType.OK:
            return 1

        if not values["exe"] or not Path(values["exe"]).is_file():
            self.error("That file no longer exists.")
            return 1

        installer = _InstallRunner(values)
        task = TaskWindow(None, f"Installing {values['name']}", installer.work,
                          on_done=self.finished)
        task.connect("destroy", Gtk.main_quit)
        Gtk.main()
        return 0

    def finished(self, manifest):
        if not isinstance(manifest, dict):
            return
        self.result = manifest
        dialog = Gtk.MessageDialog(
            modal=True, message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"{manifest['name']} is installed",
        )
        dialog.format_secondary_text(
            "It has been added to your menu under Windows Apps.\n\n"
            "Put an icon on your desktop as well?"
        )
        wants_icon = dialog.run() == Gtk.ResponseType.YES
        dialog.destroy()
        if wants_icon:
            core.write_desktop_shortcut(manifest)

    def error(self, message):
        dialog = Gtk.MessageDialog(
            modal=True, message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text=message,
        )
        dialog.run()
        dialog.destroy()


class _InstallRunner:
    """Shared install logic, so the wizard and the main window agree."""

    def __init__(self, values):
        self.values = values

    def work(self, task):
        import datetime
        import shutil as sh
        import time

        values = self.values
        exe = Path(values["exe"]).resolve()
        name = values["name"] or core.name_from_filename(exe.stem)
        slug = core.slugify(name)
        target = core.app_dir(slug)
        if target.exists():
            sh.rmtree(target)

        prefix = target / "prefix"
        log_path = target / "logs" / "install.log"
        arch = "win32" if values["arch"] == "32" else "win64"
        verbs = core.PRESETS.get(values["preset"], [])

        task.set_status("Creating an isolated Wine prefix...")
        core.create_prefix(prefix, values["runner"], arch, log_path, on_line=task.log)

        if verbs:
            task.set_status(f"Installing runtimes: {', '.join(verbs)}")
            task.log("This downloads from Microsoft and can take several minutes.")
            core.run_winetricks(prefix, values["runner"], verbs, log_path, on_line=task.log)

        task.set_status(f"Setting Windows version to {values['winver']}")
        core.set_winver(prefix, values["runner"], values["winver"], log_path, on_line=task.log)

        started = time.time()
        env, wine = core.wine_env(prefix, values["runner"])

        if values["portable"]:
            dest_dir = prefix / "drive_c" / "apps" / slug
            dest_dir.mkdir(parents=True, exist_ok=True)
            for item in exe.parent.iterdir():
                destination = dest_dir / item.name
                if item.is_dir():
                    sh.copytree(item, destination, dirs_exist_ok=True)
                else:
                    sh.copy2(item, destination)
            main_exe = dest_dir / exe.name
        else:
            task.set_status("Running the installer - complete its wizard as usual")
            core.stream([wine, str(exe)], env=env, cwd=exe.parent, log_path=log_path, on_line=task.log)
            if not core.wait_idle(env):
                task.log("The installer handed off to the app - carrying on.")
            task.set_status("Looking for the installed program...")
            candidates = core.find_candidates(prefix, since=started)
            if not candidates:
                task.log("No installed executable found in the prefix.")
                return None
            main_exe = candidates[0]
            task.log(f"Main executable: {main_exe}")

        manifest = {
            "slug": slug, "name": name, "exe": str(main_exe), "args": [],
            "workdir": str(main_exe.parent), "prefix": str(prefix),
            "runner": values["runner"], "arch": arch, "winver": values["winver"],
            "tricks": verbs, "env": {}, "source": str(exe),
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        core.save_app(manifest)
        core.extract_icon(main_exe, target / "icon.png", slug=slug)
        core.write_desktop_entry(manifest)
        task.log(f"\nDone. '{name}' is installed.")
        return manifest


def wizard(core_module, exe_path):
    """Entry point for `exerunner open <file.exe>` with a display available."""
    global core
    core = core_module
    return Wizard(exe_path).run()


def main(core_module):
    global core
    core = core_module
    window = MainWindow()
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    window.refresh()  # re-apply empty-state visibility after show_all
    Gtk.main()
    return 0


if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import exerunner

    raise SystemExit(main(exerunner))

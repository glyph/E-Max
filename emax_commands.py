# Copyright (C) 2012
# See LICENSE.txt for details.

"""
Definitions of all commands associated with E-Max.

See C{README.rst} for details.
"""

from __future__ import unicode_literals

import os

__file__ = os.path.abspath(__file__)

from cStringIO import StringIO

import kill_ring
import emax_build_keymaps

from sublime_plugin import TextCommand, EventListener, WindowCommand
from sublime import (
    Region, OP_EQUAL, OP_NOT_EQUAL, set_timeout, set_clipboard, get_clipboard,
    ENCODED_POSITION, HIDDEN, PERSISTENT, #status_message
)


REGION_VAR = 'emax_region_active'
ENABLED_VAR = 'emax_enabled'



"""
Is emax currently enabled?
"""

EMAX_ENABLED = True


"""
Update the keymaps if this is the first time we've run.
"""

emax_build_keymaps.all_maps()


def update_status(view):
    if EMAX_ENABLED:
        status = "[E-Max: ON (C-M-S-' to deactivate)]"
    else:
        status = "[E-Max: OFF (C-M-S-' to activate)]"
    view.set_status(' emax', status)



class ToggleEmax(TextCommand):
    """
    Not everybody likes Emacs.

    This command (bound to M-C-S-' by default, which is unused in Emacs) will
    enable and disable Emax key-bindings on the fly, allowing you to
    pair-program with normal human beings who are not familiar with Emacs
    key-bindings.
    """

    def run(self, edit):
        global EMAX_ENABLED
        EMAX_ENABLED = not EMAX_ENABLED
        # need to keep the binding to turn it back on!
        emax_build_keymaps.all_maps(not EMAX_ENABLED)
        update_status(self.view)



lastText = {
    # Mapping of view ID to a string.  Really only for incremental search, but
    # may collect other small, temporary views like the input buffer if the user
    # invokes incsearch from there, as there doesn't seem to be an API for
    # determining which views are "real" and which views are like that.
}



def smellsLikeIncSearch(view):
    """
    Heuristic test for a buffer that should look more or less like the
    incremental search buffer.  Not reliable, because other views will also
    meet these criteria.
    """
    return (view.window() is not None and
            view.id() not in [x.id() for x in view.window().views()] and
            view.size() < 200)



class EmaxManager(EventListener):
    """
    This is mostly a workaround for the fact that Sublime does not appear to
    have a mechanism for window- or application-scope settings, but I really
    want to toggle an 'emax_enabled' globally.

    (Also, it observes the state of the incremental-search window, so that
    EmaxMaybeRestoreIncrementalSearch can work.)
    """

    def on_activated(self, view):
        update_status(view)


    def on_deactivated(self, view):
        if smellsLikeIncSearch(view):
            if view.size() > 0:
                lastText[view.id()] = view.substr(Region(0, view.size()))


    def on_query_context(self, view, key, operator, operand, match_all):
        if key == ENABLED_VAR:
            result = None
            if operator == OP_EQUAL:
                result = operand == EMAX_ENABLED
            if operator == OP_NOT_EQUAL:
                result = operand != EMAX_ENABLED
            return result



class EmaxBeep(TextCommand):
    """
    Almost no-op command that just displays a quick message in the status area;
    bound to commands that have no effect in order to override default
    keybindings to avoid confusing one's fingers.
    """

    def run(self, edit):
        v = self.view
        v.set_status("  beep", "*BEEP*")
        def unset():
            v.erase_status("  beep")
        set_timeout(unset, 2000)



# import pydoc

class EmaxMaybeRestoreIncrementalSearch(TextCommand):
    """
    Maybe restore the incremental search area, if it's focused and we have a
    memory of a previous value for it.
    """

    def run(self, edit, reverse=False):
        if self.view.size() == 0:
            if self.view.id() in lastText:
                self.view.insert(edit, 0, lastText[self.view.id()])
        else:
            # Note: command must be run on the *window*: running it on the view
            # runs it on the incsearch view, which apparently does nothing.
            self.view.window().run_command(
                "show_panel",
                {
                    "reverse": reverse,
                    "panel": "incremental_find",
                }
            )



class EmaxHelper(TextCommand):
    """
    Helper command with useful methods.
    """

    def each_point_do(self, thunk):
        """
        Do something for each selected region, pretending like it's an emacs-
        style 'point'.
        """
        for area in self.view.sel():
            thunk(area.end())


    def updateScroll(self, forward=True):
        if forward:
            func = max
        else:
            func = min
        pt = func(x.b for x in self.view.sel())
        self.view.show(pt)


    def region_active_p(self):
        return self.view.settings().get(REGION_VAR)


    def set_mark_command(self):
        """
        Set and activate the mark, like (set-mark-command), usually bound to
        control-space.
        """
        # Use the built-in mark ring-ish thing.  This doesn't support an
        # equivalent to (yank-pop) so I need to move to something else
        # eventually...
        self.view.run_command('set_mark')
        self.view.settings().set(REGION_VAR, True)


    def deactivate_mark(self):
        """
        Deactivate the mark, like (deactivate-mark) or (keyboard-quit), usually
        bound to C-g, will do.  Note that the context-sensitive behavior of C-g
        is not implemented here, but rather as a function of different C-g
        contexts in the .sublime-keymap files.
        """
        self.view.settings().set(REGION_VAR, False)
        self.view.run_command('clear_bookmarks', dict(name="mark"))
        # hmm. self.cmd.clear_bookmarks(name="mark") instead?
        regions = [s.b for s in self.view.sel()]
        self.view.sel().clear()
        for r in regions:
            self.view.sel().add(Region(r))



class EmaxOpenLineCommand(EmaxHelper):
    """
    Mimic 'open-line', also known as 'C-o'
    """

    def run(self, edit):
        self.each_point_do(lambda point:
                           self.view.insert(edit, point, "\n"))
        self.view.run_command("move",
                              {"by": "characters", "forward": False})



class EmaxKillRingSave(EmaxHelper):
    """
    Mimic 'kill-ring-save', also known as 'M-w'.
    """

    def run(self, edit):
        self.view.run_command('add_to_kill_ring', {"forward": False})
        self.deactivate_mark()
        set_clipboard(kill_ring.kill_ring.top())



class EmaxKillRegionCommand(EmaxHelper):
    """
    Mimic 'kill-region', also known as 'C-w'.
    """

    def run(self, edit):
        self.view.run_command('delete_to_mark')
        set_clipboard(kill_ring.kill_ring.top())
        self.deactivate_mark()
        set_clipboard(kill_ring.kill_ring.top())



class EmaxKillLine(EmaxHelper):
    """
    Mimic 'kill-line' also known as 'C-k'.
    """

    def run(self, edit):
        self.deactivate_mark()
        self.view.run_command(
            "run_macro_file",
            {"file": "Packages/Default/Delete to Hard EOL.sublime-macro"}
        )
        set_clipboard(kill_ring.kill_ring.top())

class EmaxDeleteWord(EmaxHelper):
    """
    Mimic 'delete-word' also known as 'M-d'.
    """

    def run(self, edit, **kwargs):
        self.deactivate_mark()
        self.view.run_command(
            "delete_word",
            kwargs
        )
        set_clipboard(kill_ring.kill_ring.top())


class EmaxYank(EmaxHelper):
    """
    Mimic 'yank' also known as 'C-y'.
    """
    def run(self, edit):
        clip = get_clipboard()
        if kill_ring.kill_ring.top() != clip:
            kill_ring.kill_ring.seal()
            kill_ring.kill_ring.push(clip)
        self.view.run_command("yank")



class EmaxYankPop(EmaxHelper):
    """
    Mimic 'yank-pop' also known as 'M-y'.
    """

    def run(self, edit):
        if self.view.command_history(0, True)[0] not in ('emax_yank',
                                                         'emax_yank_pop'):
            print "Previous command was not a yank."
            return
        if len(self.view.sel()) != 1:
            print "Only works with one selection."
            return
        pt = self.view.sel()[0].a
        if pt != self.view.sel()[0].b:
            print "Only works with an empty selection."
            return
        kr = kill_ring.kill_ring
        if kr.top() is not None:
            # only works for a single-point selection, but better than nothing.
            self.view.erase(edit, Region(pt, pt - len(kr.top())))
        kr.head -= 1
        kr.head %= kr.limit
        if kr.top() is not None:
            self.view.run_command("yank")



class EmaxKeyboardQuit(EmaxHelper):
    """
    Mimic 'keyboard-quit', also known as 'C-g'.

    Right now this just runs deactivate_mark, and is not context-sensitive at
    all.  See the docstring for deactivate_mark for more information about its
    limitations.
    """

    def run(self, edit):
        self.deactivate_mark()



class EmaxSetMark(EmaxHelper):
    """
    Just run 'set-mark-command'; like 'C-SPC'.
    """

    def run(self, edit):
        self.set_mark_command()



class EmaxTransposeChars(EmaxHelper):
    """
    Transpose the characters surrounding the cursor.
    """

    def run(self, edit):
        """
        Completely re-implemented since sublime won't let you transpose
        characters near a word boundary.
        """
        replace = []
        for region in self.view.sel():
            pt = region.b
            ln = self.view.line(pt)
            if pt == ln.b:
                pt -= 1
            before = Region(pt, max(0, pt - 1))
            after = Region(pt, min(self.view.size(), pt + 1))
            if before != after:
                replace.append([before, after])
        for before, after in reversed(sorted(replace)):
            aftert = self.view.substr(after)
            beforet = self.view.substr(before)
            self.view.replace(edit, after, beforet)
            self.view.replace(edit, before, aftert)



class EmaxTransposeWords(EmaxHelper):
    """
    Transpose the words surrounding the cursor.
    """

    def run(self, edit):
        """
        Sublime's word-transposition is close enough; you just have to make the
        cursor line up with its expectation.
        """
        newsels = []
        for region in self.view.sel():
            word = self.view.word(region.b)
            if region.b == word.a:
                newsels.append(word.a)
            else:
                newsels.append(word.b)
        self.view.sel().clear()
        for i in newsels:
            self.view.sel().add(Region(i, i))
        self.view.run_command("transpose")
        self.view.run_command("move", {"forward": True, "by": "words"})
        self.view.run_command("move", {"forward": True, "by": "words"})



class EmaxRebuildKeymaps(EmaxHelper):
    """
    Re-build the keymaps from within the editor.
    """

    def run(self, edit):
        emax_build_keymaps.all_maps(not EMAX_ENABLED)



class EmaxMarkWholeBuffer(EmaxHelper):
    """
    Like select_all but also set the mark.
    """

    def run(self, edit):
        self.view.run_command("move_to", {"to": "bof"})
        self.set_mark_command()
        self.view.run_command("move_to", {"to": "eof", "extend": True})



class CharacterCursor(object):
    """
    Scan through a buffer, one character at a time.
    """

    def __init__(self, backwards, index, view):
        super(CharacterCursor, self).__init__()
        self.backwards = backwards
        self.index = index
        self.view = view


    def __iter__(self):
        return self


    def peek(self):
        """
        Take a peek at the next character, without advancing the cursor.
        """
        if self.index < 0 or self.index > self.view.size():
            return ''
        return self.view.substr(self.index)


    def next(self):
        it = self.peek()
        if self.backwards:
            self.index -= 1
        else:
            self.index += 1
        if not it:
            raise StopIteration()
        return it



class LineCursor(object):
    """
    Scan through a buffer, one line at a time.
    """
    def __init__(self, backwards, index, view):
        self.backwards = backwards
        self.view = view
        self.region = view.line(index)
        self.stopped = False


    def clone(self, reverse=False):
        return self.__class__(self.backwards ^ reverse, self.region.a,
                              self.view)


    def __iter__(self):
        return self


    def next(self):
        if self.stopped:
            raise StopIteration()
        result = self.view.substr(self.region)
        if self.backwards:
            point = self.region.a - 1
        else:
            point = self.region.b + 1
        oldregion = self.region
        self.region = self.view.line(point)
        if (oldregion == self.region or
            self.region.b >= self.view.size() or
            self.region.a < 0):
            self.stopped = True
        return result



matches = {
    "[": "]",
    "'": "'",
    '"': '"',
    "{": "}",
    "(": ")",
}



rmatches = {}
def _andReverse():
    for m in matches:
        rmatches[matches[m]] = m
_andReverse()
import string
whitespace = string.whitespace.decode("latin1")



def scanOneSexp(scanner, matcher, rmatcher):
    stack = []
    ever = False
    inword = False
    backslash = False
    def isquote(x):
        return x in matcher and x in rmatcher
    def inquotes():
        return isquote(stack[-1])
    for c in scanner:
        # print 'SCANNED', repr(c)
        # print 'STACK:', stack
        if not stack:
            if ever:
                # print 'STACK EMPTY AND EVER STACK, DONE'
                return True
            if inword:
                if c in whitespace or c in matcher or c in rmatcher:
                    # one word: no parens on stack: done.
                    # print 'WORD END'
                    return True
                else:
                    # print 'WORD CONT'
                    continue
            else:
                if c in matcher:
                    # print "STACK PUSH"
                    ever = True
                    stack.append(c)
                    continue
                elif c in rmatcher:
                    # close brace/bracket/paren at top scope; no sexp to jump
                    # over.
                    # print "CLOSE_AT_TOP"
                    return False
                if c not in whitespace:
                    # print "WORD START"
                    inword = True
        else:
            if inquotes() and not scanner.backwards:
                if backslash:
                    backslash = False
                    continue
                elif c == '\\':
                    backslash = True
                    continue
            if c in rmatcher:
                if rmatcher[c] == stack[-1]:
                    # print "PAREN MATCH", # stack.pop()
                    if ( inquotes() and scanner.backwards
                         and scanner.peek() == '\\' ):
                        continue
                    stack.pop()
                    continue
                elif not inquotes() and not isquote(c):
                    # mismatched parens
                    # print "MISMATCH"
                    return False
            if c in matcher:
                if not inquotes():
                    # print 'STACK PUSH'
                    stack.append(c)
    else:
        if ever and not stack:
            return True
        # print "SUDDEN EXIT"
        return False
    # print 'UNREACHABLE'



class EmaxMoveSexp(EmaxHelper):
    """
    Move the cursor forward or backward by one S-expression.
    """

    def run(self, edit, forward=True, extend=False):
        ns = []
        if forward:
            matcher = matches
            rmatcher = rmatches
            backward = False
            adjust = -1
        else:
            matcher = rmatches
            rmatcher = matches
            backward = True
            adjust = 2
        for s in self.view.sel():
            cursor = CharacterCursor(backward, s.b - backward, self.view)
            if scanOneSexp(cursor, matcher, rmatcher):
                if extend:
                    a = s.a
                else:
                    a = cursor.index + adjust
                ns.append(Region(a, cursor.index + adjust))
            else:
                ns.append(s)
        self.view.sel().clear()
        for r in ns:
            self.view.sel().add(r)
        self.updateScroll(forward)



class EmaxSaveAndClose(EmaxHelper):
    """
    Save and close in one command.

    This is to emulate the log-edit-done style commands that come along with
    dvc or vc or psvn; save and close the buffer so that an external process
    can get to it.  Really, this should be bound only in temporary buffers
    started by subl.
    """

    def run(self, edit):
        self.view.run_command("save")
        self.view.window().run_command("close")



class EmaxJumpToHunk(EmaxHelper):
    """
    Jump to a hunk of a diff.
    """

    def run(self, edit):
        """
        Based on the current position of the cursor, jump to the appropriate
        file/line combination.
        """
        offt = -1
        havehunk = False
        for line in LineCursor(True, self.view.sel()[0].b, self.view):
            if line.startswith("@@"):
                if havehunk:
                    continue
                havehunk = True
                atat, minus, plus, atat = line.split()
                baseline = int(plus[1:].split(",")[0])
                realline = baseline + offt
            elif line.startswith("+++"):
                fname = line[4:].split("\t")[0]
                # definitely set by now, but ugh
                self.view.window().open_file(
                    # This should probably try multiple locations, looking for
                    # files which actually exist, since a shell command like
                    # "foo | subl" always puts the output into a buffer in /tmp,
                    # and we can no longer tell which folder it applies to.
                    os.path.join(
                        self.view.window().folders()[0], fname
                    ) + ":" + str(realline),
                    ENCODED_POSITION
                )
                break
            elif not havehunk and line.startswith(" ") or line.startswith("+"):
                offt += 1
            elif line.startswith("-"):
                pass
        else:
            print "No hunk found."



class EmaxExchangePointAndMark(EmaxHelper):
    """
    Replication of 'exchange-point-and-mark', i.e. C-x C-x.
    """

    def run(self, edit):
        """
        Exchange the point and the mark.
        """
        marks = self.view.get_regions("mark")
        newsel = []
        newmark = []
        for s in self.view.sel():
            for mark in marks:
                if mark.a == mark.b == s.a:
                    newsel.append(Region(s.b, s.a))
                    newmark.append(Region(s.b, s.b))
        if newsel:
            self.view.erase_regions("mark")
            self.view.add_regions(
                "mark", newmark, "mark", "dot", HIDDEN | PERSISTENT
            )
            self.view.sel().clear()
            for reg in newsel:
                self.view.sel().add(reg)
            self.updateScroll()



def overlapping(view, point, scopeNames):
    """
    Extract a region that defines a scope, whose name matches one of a given
    set of scope names, that overlaps the given point.

    @param view: a sublime view
    @type view: L{sublime.View}

    @param point: an offset into the view, the one we're looking for in a scope
        (usually representative of a cursor / single-element selection)
    @type point: L{int}

    @param scopeNames: a set of strings naming scopes.
    @type scopeNames: C{iterable} of L{unicode}

    @return: a region that spans one of the named scopes.
    @rtype: L{sublime.Region} or L{NoneType}
    """
    for name in scopeNames:
        for region in view.find_by_selector(name):
            if region.a <= point <= region.b:
                return region



class EmaxFillParagraph(TextCommand):
    """
    Similar to 'fill-paragraph', i.e. M-q.

    Like fill-paragraph, this has some mode-specific logic.  Currently it only
    has some Python-aware stuff, for working on projects like U{Twisted
    <http://twistedmatrix.com/>} which use Epydoc formatted docstrings.
    """

    def run(self, edit):
        """
        Fill a paragraph around the first point.
        """
        scopes = self.view.scope_name(self.view.sel()[0].a).split()
        desired = set([
            'string.quoted.double.block.python',
            'string.quoted.single.block.python',
        ])

        if desired.intersection(set(scopes)):
            from epywrap import wrapPythonDocstring
            orig = self.view.sel()[0]
            scope = overlapping(self.view, orig.a, desired)
            startline = self.view.substr(self.view.line(scope.a))
            indentation = startline[:len(startline) - len(startline.lstrip())]
            torepl = Region(scope.a + 3, scope.b - 3)
            origPoint = orig.a - torepl.a
            io = StringIO()
            origText = self.view.substr(torepl)
            lineLength = self.view.settings().get("wrap_width")
            if not lineLength:
                lineLength = 79
            newPoint = wrapPythonDocstring(
               origText, io, indentation, point=origPoint, width=lineLength
            ) + torepl.a
            val = io.getvalue()
            if val != origText:
                self.view.replace(edit, torepl, val)
                # try to put the selection back at least vaguely where it was.
                self.view.sel().clear()
                self.view.sel().add(Region(newPoint, newPoint))
                self.view.show(newPoint)
        else:
            # this should _really_ be accomplished via a mapping context, but I
            # cannot figure out for the life of me how selector matching in
            # .sublime-keymap files is supposed to go.
            self.view.run_command("wrap_lines")



class EmaxOtherWindowCommand(WindowCommand):
    """
    Similar to 'other-window', i.e. C-x C-o.

    Move the focus to the next sublime group, because this is the closest
    analogue to the next Emacs 'window'.
    """
    def run(self):
        """
        Focus the next group.
        """
        self.window.focus_group(
            (self.window.active_group() + 1) % self.window.num_groups()
        )



class EmaxSplitWindowRightCommand(WindowCommand):
    """
    Similar to 'split-window-right', i.e. C-x 2.

    Divide the current window into half inserting a new window on the right.
    """

    layout_key = 'cols'
    new_cell_indices = [0, 2]

    def run(self):
        active = self.window.active_group()

        layout = self.window.get_layout()

        pcnts = layout[self.layout_key]

        pcnts.insert(active + 1,
                     pcnts[active] + (pcnts[active + 1] - pcnts[active]) * 0.5)

        current_cell = layout['cells'][active]

        next_cell = current_cell[:]
        for i in self.new_cell_indices:
            next_cell[i] += 1

        layout['cells'].insert(active + 1, next_cell)

        self.window.set_layout(layout)



class EmaxSplitWindowBelowCommand(EmaxSplitWindowRightCommand):
    """
    Similar to 'split-window-below', i.e. C-x 3.

    Divide the current window into half inserting a new window below the
    current window.
    """

    layout_key = 'rows'
    new_cell_indices = [1, 3]


E-Max
=====

There are several plugins that emulate other editors' keybindings for Sublime
Text 2, but only E-Max gives you the *maximum* amount of E...macs.

Rather than just emulating a few cursor-movement keystrokes inconsistently
across platforms, this plugin aims to comprehensively emulate the behavior
you're used to, mapping the same relative physical keys the same way on each
platform that Sublime supports, so that a true Emacs veteran will instantly feel
at home.  Kill-ring, swap point and mark, the meta key in the right position
(under your thumb), cancel with C-g, isearch with recall: it's all (mostly)
there.  And if it's not, feel free to send a pull request!

As it was written by a Python programmer, this also includes some Python-specific emacs
goodies, like docstring wrapping and some python-specific
bindings, such as emulation of python-shift-left/python-shift-right.

E-Max was also designed with courtesy in mind.  Pair programming partner doesn't
like Emacs?  No problem!  Just hit a keystroke that all we keyboard
contortionists will have no difficulty with – control-meta-shift-quote – and you
can instantly disable all emacs-like behavior and go back to the platform-
variable Sublime Text defaults.

Installation
------------

Copy all files from this directory into a directory called E-Max in your
Sublime Text 2 Packages directory.  If you use git, you can do that very
easily:

  $ cd ~/config/sublime-text-2/Packages
  $ git clone https://github.com/glyph/E-Max.git

If you do this correctly, you'll then see "E-Max: ON" in the mode line in
Sublime.

On Mac OS X and Windows the Packages directory is located elsewhere. You
can determine its location from inside Sublime: use "View" / "Show Console"
to open the console, paste the command sublime.packages_path() and then
press ENTER.


Copyright © 2012

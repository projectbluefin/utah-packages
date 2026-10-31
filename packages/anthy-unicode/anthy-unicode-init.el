;;; anthy-unicode-init.el --- Autoload anthy-unicode  -*- lexical-binding: t -*-

;; Copyright (C) 2001 - 2007 KMC(Kyoto University Micro Computer Club)
;; Copyright (c) 2005 - 2026 Red Hat, Inc.
;; Copyright (C) 2019 - 2026 Takao Fujiwara <takao.fujiwara1@gmail.com>

;; Author: Yusuke Tabata<yusuke@kmc.gr.jp>
;;         Tomoharu Ugawa
;;         Norio Suzuki <suzuki@sanpobu.net>
;; Maintainer: Akira TAGOH <tagoh@redhat.com>
;;             Takao Fujiwara <takao.fujiwara1@gmail.com>
;; Keywords: japanese
;; SPDX-License-Identifier: LGPL-2.0-or-later

;;; Commentary:
;;
;; Program for using the Anthy Kana-Kanji conversion engine from Emacs.
;; It handles text conversion by launching the 'anthy-agent-unicode' command
;; and communicating with it via pipes.

;; You can enable anthy-unicode on Emacs and XEmacs with the following setting:
;; (set-input-method 'japanese-anthy-unicode)

;;; Code:
(if (featurep 'xemacs)
    (setq load-path (cons "/usr/share/xemacs/xemacs-packages/lisp/anthy-unicode" load-path))
  (setq load-path (cons "/usr/share/emacs/site-lisp/anthy-unicode" load-path)))
(autoload 'anthy-unicode-leim-activate "anthy-unicode" nil t)
(register-input-method "japanese-anthy-unicode" "Japanese"
		       'anthy-unicode-leim-activate "[anthy-unicode]"
		       "Anthy Unicode Kana Kanji conversion system")

;;; anthy-unicode-init.el ends here

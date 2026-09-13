;;; desktop-entry-mode-init.el --- Autoload desktop-entry-mode  -*- lexical-binding: t; -*-

;;; Commentary:
;;
;; Autoload desktop-entry-mode

;;; Code:

(autoload 'desktop-entry-mode "desktop-entry-mode" "Desktop Entry mode" t)
(add-to-list 'auto-mode-alist '("\\.desktop\\(\\.in\\)?$" . desktop-entry-mode))

;;; desktop-entry-mode-init.el ends here

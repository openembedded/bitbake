" Only do this when not done yet for this buffer
if exists("b:did_ftplugin")
  finish
endif

" Don't load another plugin for this buffer
let b:did_ftplugin = 1

let b:undo_ftplugin = "setl inc< pa< cms< sts< sw< et< sua<"

setlocal include=^\s*\(inherit\|include\|require\)
" Yocto, Petalinux
setlocal path=.,,meta/classes*,components/yocto/layers/**/classes*
setlocal commentstring=#\ %s
setlocal softtabstop=4 shiftwidth=4 expandtab
setlocal suffixesadd+=.bb,.bbclass

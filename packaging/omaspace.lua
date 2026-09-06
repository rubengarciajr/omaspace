-- OmaSpace: user-owned integration; packaged Omarchy files stay untouched.
-- SUPER+UP previously focused the window above.
hl.unbind("SUPER + UP")
o.bind("SUPER + UP", "OmaSpace workspace overview", "omaspace toggle")
hl.layer_rule({ match = { namespace = "^omaspace$" }, blur = true, ignore_alpha = 0.05, no_anim = true })
o.exec_on_start("omaspace-start")

CLEANFILES = \
	vdsm-api.html \
	$(NULL)

EXTRA_DIST = \
	process-schema.py \
	vdsmapi-schema.json \
	$(NULL)

dist_vdsm_PYTHON = \
	BindingJsonRpc.py \
	Bridge.py \
	$(NULL)

dist_vdsm_DATA = \
	vdsmapi-schema.json \
	$(NULL)

dist_python_PYTHON = \
	vdsmapi.py \
	$(NULL)

nodist_noinst_DATA = \
	vdsm-api.html \
	$(NULL)

vdsm-api.html: process-schema.py vdsmapi-schema.json
	@echo "  Generate $@"
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$(srcdir)/../lib \
	    $(PYTHON) $(srcdir)/process-schema.py \
	              $(srcdir)/vdsmapi-schema.json $(srcdir)/$@

all-local: \
	$(nodist_noinst_DATA)

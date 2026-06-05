PYTHON ?= python
AWS_REGION ?= ap-south-1
PIPELINE_NAME ?= sagemaker-mlops-lab

.PHONY: install validate test run-pipeline

install:
	$(PYTHON) -m pip install -r requirements.txt

validate:
	$(PYTHON) scripts/validate_lab.py

test:
	pytest scripts/test.py

run-pipeline:
	$(PYTHON) scripts/run_pipeline.py --region $(AWS_REGION) --pipeline-name $(PIPELINE_NAME) --start

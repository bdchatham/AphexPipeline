from setuptools import setup, find_packages

setup(
    name='aphex-pipeline-scripts',
    version='1.0.0',
    description='AphexPipeline workflow generation and execution scripts',
    packages=find_packages(),
    python_requires='>=3.9',
    install_requires=[
        'boto3>=1.28.0',
        'PyYAML>=6.0',
        'jsonschema>=4.19.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'hypothesis>=6.88.0',
            'mypy>=1.5.0',
            'types-PyYAML>=6.0.0',
        ],
    },
)

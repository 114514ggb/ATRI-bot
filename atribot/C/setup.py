from setuptools import setup, Extension
import sys

def get_compile_args():
    """根据平台和编译器选择合适的编译参数"""
    if sys.platform == 'win32':
        # Windows MSVC编译器
        return ['/O2', '/favor:INTEL64']
    else:
        # Unix-like系统 (GCC/Clang)
        return ['-O3', '-march=native']

levenshtein_module = Extension(
    'levenshtein',
    sources=['levenshtein.c'],
    include_dirs=[],
    libraries=[],
    library_dirs=[],
    extra_compile_args=get_compile_args(), 
    extra_link_args=[]
)

setup(
    name='levenshtein',
    version='1.0.0',
    description='Fast Levenshtein distance implementation in C',
    ext_modules=[levenshtein_module],
    package_data={
        '': ['Levenshtein.pyi'],
    },
    include_package_data=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: C',
    ],
    python_requires='>=3.6',
)
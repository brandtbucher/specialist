# pylint: disable = missing-module-docstring
import pathlib
import setuptools  # type: ignore

README = pathlib.Path(__file__).parent / "README.md"
setuptools.setup(
    author="Brandt Bucher",
    author_email="brandt@python.org",
    description="Visualize CPython 3.11's specializing, adaptive interpreter.",
    entry_points={"console_scripts": ["specialist=specialist:main"]},
    license="MIT",
    long_description=README.read_text(),
    long_description_content_type="text/markdown",
    name="specialist",
    py_modules=["specialist"],
    python_requires=">=3.11",
    url="https://github.com/brandtbucher/specialist",
    version="0.2.2",
)

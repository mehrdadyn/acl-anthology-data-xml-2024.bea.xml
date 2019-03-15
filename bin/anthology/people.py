# Marcel Bollmann <marcel@bollmann.me>, 2019

from collections import defaultdict, Counter
from slugify import slugify
import yaml
from .formatter import bibtex_encode
from .venues import VenueIndex

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


class PersonName:
    first, last, jr = "", "", ""

    def __init__(self, first, last, jr):
        self.first = first.strip()
        self.last = last.strip()
        self.jr = jr.strip()

    def from_element(person_element):
        first, last, jr = "", "", ""
        for element in person_element:
            tag = element.tag
            # These are guaranteed to occur at most once by the schema
            if tag == "first":
                first = element.text or ""
            elif tag == "last":
                last = element.text or ""
            elif tag == "jr":
                jr = element.text or ""
        return PersonName(first, last, jr)

    def from_repr(repr_):
        parts = repr_.split(" || ")
        first = parts[0]
        last  = parts[1] if len(parts) > 1 else ""
        jr    = parts[2] if len(parts) > 2 else ""
        return PersonName(first, last, jr)

    @property
    def full(self):
        return "{} {}{}".format(self.first, self.last, self.jr).strip()

    @property
    def id_(self):
        return repr(self)

    def as_bibtex(self):
        return bibtex_encode("{}{}, {}".format(self.last, self.jr, self.first))

    def as_dict(self):
        return {
            "first": self.first,
            "last": self.last,
            "jr": self.jr,
            "full": self.full,
        }

    def __eq__(self, other):
        return (
            (self.first == other.first)
            and (self.last == other.last)
            and (self.jr == other.jr)
        )

    def __str__(self):
        return self.full

    def __repr__(self):
        if self.jr:
            return "{} || {} || {}".format(self.first, self.last, self.jr)
        elif self.first:
            return "{} || {}".format(self.first, self.last)
        else:
            return self.last

    def __hash__(self):
        return hash(repr(self))


class PersonIndex:
    """Keeps an index of persons and their associated papers."""

    def __init__(self, srcdir=None):
        self.names = {}  # maps name strings to PersonName objects
        self.variants = {}  # maps name strings to canonical name strings
        self._all_slugs = set([""])
        self.slugs = {}  # maps name strings to unique slugs
        self.coauthors = defaultdict(
            Counter
        )  # maps name strings to co-author name strings
        self.papers = defaultdict(lambda: defaultdict(list))
        if srcdir is not None:
            self.load_variant_list(srcdir)

    def load_variant_list(self, directory):
        with open("{}/name_variants.yaml".format(directory), "r") as f:
            name_dict = yaml.load(f, Loader=Loader)
            for canonical, variants in name_dict.items():
                for variant in variants:
                    self.variants[variant] = canonical

    def register(self, name: PersonName, paper, role):
        """Adds a name to the index, associates it with the given paper ID and role, and returns the name's unique representation."""
        assert isinstance(name, PersonName), "Expected PersonName, got {} ({})".format(
            type(name), repr(name)
        )
        name = self.get_canonical_variant(name)
        name_repr = repr(name)
        if name_repr not in self.names:
            self.names[name_repr] = name
            # Make sure to generate a site-wide unique slug
            slug, i = slugify(name_repr), 0
            while slug in self._all_slugs:
                i += 1
                slug = "{}{}".format(slugify(name_repr), i)
            self._all_slugs.add(slug)
            self.slugs[name] = slug
        # Register paper
        self.papers[name][role].append(paper.full_id)
        # Register co-author(s)
        for author in paper.get(role):
            author = self.get_canonical_variant(author)
            if author != name:
                self.coauthors[name][author] += 1
        # Return string representation
        return name_repr

    def items(self):
        return self.names.items()

    def __len__(self):
        return len(self.names)

    def get_canonical_variant(self, name):
        """Maps a name to its canonical variant."""
        name_repr = repr(name)
        if name_repr in self.variants:
            return PersonName.from_repr(self.variants[name_repr])
        return name

    def get_slug(self, name):
        name = self.get_canonical_variant(name)
        return self.slugs[name]

    def get_papers(self, name, role=None):
        name = self.get_canonical_variant(name)
        if role is None:
            return [p for p_list in self.papers[name].values() for p in p_list]
        return self.papers[name][role]

    def get_coauthors(self, name):
        name = self.get_canonical_variant(name)
        return self.coauthors[name].items()

    def get_venues(self, vidx: VenueIndex, name):
        """Get a list of venues a person has published in, with counts."""
        venues = Counter()
        for paper in self.get_papers(name):
            for venue in vidx.get_associated_venues(paper):
                venues[venue] += 1
        return venues

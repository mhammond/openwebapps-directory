"""Persistence for applications"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, UnicodeText, Unicode
from sqlalchemy import and_, or_, not_, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from directory.util import make_slug, get_icon, origin_to_key, json
from datetime import datetime


Session = sessionmaker()
Base = declarative_base()


class Application(Base):
    """Represents one application in the directory"""

    __tablename__ = 'application'
    id = Column(Integer, primary_key=True)
    origin = Column(String(120), nullable=False, unique=True)
    # Derivative of origin (used for lookup):
    origin_key = Column(String(120), nullable=False, unique=True)
    manifest_json = Column(UnicodeText, nullable=False)
    manifest_fetched = Column(DateTime)
    manifest_url = Column(UnicodeText)
    name = Column(UnicodeText, nullable=False)
    # Derivative of name (used for URLs, *not* lookup):
    slug = Column(UnicodeText, nullable=False)
    description = Column(UnicodeText)
    icon_url = Column(UnicodeText)
    # These are represented by |keyword1|keyword2|:
    keywords_denormalized = Column(UnicodeText)
    featured = Column(Boolean, default=False)
    featured_sort = Column(Float)
    featured_start = Column(DateTime)
    featured_end = Column(DateTime)
    hide = Column(Boolean, default=False)
    added = Column(DateTime, default=datetime.now)
    last_updated = Column(DateTime, onupdate=datetime.now)

    def __init__(self, origin, manifest_json, manifest_url, manifest_fetched,
                 name, description, icon_url, keywords=None,
                 featured=False, featured_sort=None, featured_start=None,
                 featured_end=None, hide=False):
        self.origin = origin
        self.manifest_json = manifest_json
        self.manifest_url = manifest_url
        self.manifest_fetched = manifest_fetched
        self.name = name
        self.description = description
        self.icon_url = icon_url
        if keywords is not None:
            self.keywords = keywords
        self.featured = featured
        self.featured_sort = featured_sort
        self.featured_start = featured_start
        self.featured_end = featured_end
        self.hide = hide
        ## FIXME: there must be a way to do this more automatically?
        self.set_origin_key()
        self.set_slug()

    @property
    def keywords(self):
        return [w for w in self.keywords_denormalized.split('|')
                if w]

    @keywords.setter
    def keywords(self, words):
        assert not isinstance(words, basestring)
        words = [w.strip().lower().replace('|', ' ')
                 for w in words]
        words = [w for w in words if w]
        value = '|' + '|'.join(words) + '|'
        self.keywords_denormalized = value

    def set_origin_key(self):
        """This sets the origin_key value based on the origin"""
        self.origin_key = origin_to_key(self.origin)

    def set_slug(self):
        self.slug = make_slug(self.name)

    def __repr__(self):
        return '<Application %s %s>' % (
            self.id or 'unsaved', self.origin)

    @classmethod
    def from_manifest(cls, manifest, manifest_fetched, manifest_url, origin,
                      session=None):
        obj = cls(
            origin=origin,
            manifest_json=unicode(json.dumps(manifest)),
            manifest_fetched=manifest_fetched,
            manifest_url=manifest_url,
            name=manifest['name'],
            description=manifest.get('description'),
            icon_url=get_icon(manifest.get('icons'), origin),
            )
        keywords = manifest.get('experimental', {}).get('keywords')
        if keywords:
            obj.keywords = keywords
        else:
            obj.keywords = [u'uncategorized']
        if session is not None:
            session.add(obj)
        Keyword.add_words(obj.keywords, session=session)
        return obj

    def update_from_manifest(self, manifest, manifest_fetched, manifest_url,
                             origin=None, session=None):
        if origin is not None and not self.origin == origin:
            raise ValueError(
                "You cannot update the origin")
        self.manifest_json = unicode(json.dumps(manifest))
        self.manifest_fetched = manifest_fetched
        self.manifest_url = manifest_url
        self.name = manifest['name']
        self.description = manifest.get('description')
        self.icon_url = get_icon(manifest.get('icons'), self.origin)
        keywords = manifest.get('experimental', {}).get('keywords')
        if keywords:
            self.keywords = keywords
        self.set_slug()
        if session:
            session.add(self)
        Keyword.add_words(self.keywords, session=session)
        return self

    @property
    def manifest(self):
        return json.loads(self.manifest_json)

    @manifest.setter
    def manifest(self, value):
        self.manifest_json = unicode(json.dumps(value))

    @property
    def manifest_developer(self):
        return self.manifest.get('developer')

    @classmethod
    def get(cls, origin_key, session=None):
        if session is None:
            session = Session()
        q = session.query(cls).filter(cls.origin_key == origin_key)
        try:
            return q.one()
        except NoResultFound:
            return None

    @classmethod
    def by_origin(cls, origin, session=None):
        if session is None:
            session = Session()
        q = session.query(cls).filter(cls.origin == origin)
        try:
            return q.one()
        except NoResultFound:
            return None

    @property
    def url(self):
        return '/app/%s/%s' % (self.origin_key, self.slug)

    @classmethod
    def search(cls, query, hidden=False, session=None):
        quoted_query = '%' + query.replace('%', '%%') + '%'
        if session is None:
            session = Session()
        q = session.query(cls)
        if not hidden:
            q = q.filter(not_(cls.hide))
        q = q.filter(or_(
            cls.name.ilike(quoted_query),
            cls.description.ilike(quoted_query),
            cls.keywords_denormalized.like(quoted_query)))
        return q

    @classmethod
    def recent(cls, count, hidden=False, session=None):
        if session is None:
            session = Session()
        q = session.query(cls)
        if not hidden:
            q = q.filter(not_(cls.hide))
        return q.order_by(desc(cls.added)).limit(count)

    @classmethod
    def featured_apps(cls, hidden=False, session=None):
        if session is None:
            session = Session()
        now = datetime.now()
        q = session.query(cls)
        if not hidden:
            q = q.filter(not_(cls.hide))
        q = q.filter(and_(
            cls.featured,
            or_(cls.featured_start == None,
                cls.featured_start <= now),
            or_(cls.featured_end == None,
                cls.featured_end >= now))).order_by(
            cls.featured_sort)
        return q

    @classmethod
    def search_keyword(cls, keyword, hidden=False, session=None):
        if session is None:
            session = Session()
        keyword = keyword.lower()
        keyword = keyword.replace('%', '%%').replace('|', ' ')
        match = '%|' + keyword + '|%'
        q = session.query(cls)
        if not hidden:
            q = q.filter(not_(cls.hide))
        q = q.filter(
            cls.keywords_denormalized.like(match))
        return q


class Keyword(Base):
    """Represents available keywords (keywords some application has used)

    This doesn't map to applications, it only is used to generate the
    list of all keywords."""

    __tablename__ = 'keyword'
    word = Column(Unicode(100), primary_key=True)
    description = Column(UnicodeText)
    hide = Column(Boolean, default=False)

    def __init__(self, word):
        self.word = word

    def __repr__(self):
        return '<Keyword %s>' % self.word

    @classmethod
    def get(cls, word, session=None):
        if session is None:
            session = Session()
        try:
            return session.query(cls).filter(cls.word == word).one()
        except NoResultFound:
            return None

    @classmethod
    def add_words(cls, words, session=None):
        assert all(isinstance(o, unicode) for o in words), words
        leftover = set(words)
        this_session = session or Session()
        q = this_session.query(Keyword).filter(
            cls.word.in_(words))
        for match in q:
            if match.word in leftover:
                leftover.remove(match.word)
        for word in leftover:
            k = cls(word)
            this_session.add(k)
        if session is None:
            this_session.commit()

    @classmethod
    def all_words(cls, session=None):
        if session is None:
            session = Session()
        return session.query(cls).filter(not_(cls.hide)).order_by(cls.word)

    @classmethod
    def trim_keywords(cls, session=None):
        this_session = session or Session()
        unused = dict(
            (k.word, k) for k in this_session.query(cls))
        for app in this_session.query(Application):
            for word in app.keywords:
                if word in unused:
                    del unused[word]
        for obj in unused.values():
            this_session.delete(obj)
        if session is None:
            this_session.commit()
        return unused

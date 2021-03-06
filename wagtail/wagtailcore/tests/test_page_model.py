import warnings

from django.test import TestCase, Client
from django.test.utils import override_settings
from django.http import HttpRequest, Http404

from wagtail.utils.deprecation import RemovedInWagtail06Warning

from wagtail.wagtailcore.models import Page, Site
from wagtail.tests.models import EventPage, EventIndex, SimplePage, PageWithOldStyleRouteMethod


class TestSiteRouting(TestCase):
    fixtures = ['test.json']

    def setUp(self):
        self.default_site = Site.objects.get(is_default_site=True)
        events_page = Page.objects.get(url_path='/home/events/')
        about_page = Page.objects.get(url_path='/home/about-us/')
        self.events_site = Site.objects.create(hostname='events.example.com', root_page=events_page)
        self.alternate_port_events_site = Site.objects.create(hostname='events.example.com', root_page=events_page, port='8765')
        self.about_site = Site.objects.create(hostname='about.example.com', root_page=about_page)
        self.unrecognised_port = '8000'
        self.unrecognised_hostname = 'unknown.site.com'

    def test_no_host_header_routes_to_default_site(self):
        # requests without a Host: header should be directed to the default site
        request = HttpRequest()
        request.path = '/'
        self.assertEqual(Site.find_for_request(request), self.default_site)

    def test_valid_headers_route_to_specific_site(self):
        # requests with a known Host: header should be directed to the specific site
        request = HttpRequest()
        request.path = '/'
        request.META['HTTP_HOST'] = self.events_site.hostname
        request.META['SERVER_PORT'] = self.events_site.port
        self.assertEqual(Site.find_for_request(request), self.events_site)

    def test_ports_in_request_headers_are_respected(self):
        # ports in the Host: header should be respected
        request = HttpRequest()
        request.path = '/'
        request.META['HTTP_HOST'] = self.alternate_port_events_site.hostname
        request.META['SERVER_PORT'] = self.alternate_port_events_site.port
        self.assertEqual(Site.find_for_request(request), self.alternate_port_events_site)

    def test_unrecognised_host_header_routes_to_default_site(self):
        # requests with an unrecognised Host: header should be directed to the default site
        request = HttpRequest()
        request.path = '/'
        request.META['HTTP_HOST'] = self.unrecognised_hostname
        request.META['SERVER_PORT'] = '80'
        self.assertEqual(Site.find_for_request(request), self.default_site)

    def test_unrecognised_port_and_default_host_routes_to_default_site(self):
        # requests to the default host on an unrecognised port should be directed to the default site
        request = HttpRequest()
        request.path = '/'
        request.META['HTTP_HOST'] = self.default_site.hostname
        request.META['SERVER_PORT'] = self.unrecognised_port
        self.assertEqual(Site.find_for_request(request), self.default_site)

    def test_unrecognised_port_and_unrecognised_host_routes_to_default_site(self):
        # requests with an unrecognised Host: header _and_ an unrecognised port
        # hould be directed to the default site
        request = HttpRequest()
        request.path = '/'
        request.META['HTTP_HOST'] = self.unrecognised_hostname
        request.META['SERVER_PORT'] = self.unrecognised_port
        self.assertEqual(Site.find_for_request(request), self.default_site)

    def test_unrecognised_port_on_known_hostname_routes_there_if_no_ambiguity(self):
        # requests on an unrecognised port should be directed to the site with
        # matching hostname if there is no ambiguity
        request = HttpRequest()
        request.path = '/'
        request.META['HTTP_HOST'] = self.about_site.hostname
        request.META['SERVER_PORT'] = self.unrecognised_port
        self.assertEqual(Site.find_for_request(request), self.about_site)

    def test_unrecognised_port_on_known_hostname_routes_to_default_site_if_ambiguity(self):
        # requests on an unrecognised port should be directed to the default
        # site, even if their hostname (but not port) matches more than one
        # other entry
        request = HttpRequest()
        request.path = '/'
        request.META['HTTP_HOST'] = self.events_site.hostname
        request.META['SERVER_PORT'] = self.unrecognised_port
        self.assertEqual(Site.find_for_request(request), self.default_site)

    def test_port_in_http_host_header_is_ignored(self):
        # port in the HTTP_HOST header is ignored
        request = HttpRequest()
        request.path = '/'
        request.META['HTTP_HOST'] = "%s:%s" % (self.events_site.hostname, self.events_site.port)
        request.META['SERVER_PORT'] = self.alternate_port_events_site.port
        self.assertEqual(Site.find_for_request(request), self.alternate_port_events_site)


class TestRouting(TestCase):
    fixtures = ['test.json']

    # need to clear urlresolver caches before/after tests, because we override ROOT_URLCONF
    # in some tests here
    def setUp(self):
        from django.core.urlresolvers import clear_url_caches
        clear_url_caches()

    def tearDown(self):
        from django.core.urlresolvers import clear_url_caches
        clear_url_caches()

    def test_urls(self):
        default_site = Site.objects.get(is_default_site=True)
        homepage = Page.objects.get(url_path='/home/')
        christmas_page = Page.objects.get(url_path='/home/events/christmas/')

        # Basic installation only has one site configured, so page.url will return local URLs
        self.assertEqual(homepage.full_url, 'http://localhost/')
        self.assertEqual(homepage.url, '/')
        self.assertEqual(homepage.relative_url(default_site), '/')

        self.assertEqual(christmas_page.full_url, 'http://localhost/events/christmas/')
        self.assertEqual(christmas_page.url, '/events/christmas/')
        self.assertEqual(christmas_page.relative_url(default_site), '/events/christmas/')

    def test_urls_with_multiple_sites(self):
        events_page = Page.objects.get(url_path='/home/events/')
        events_site = Site.objects.create(hostname='events.example.com', root_page=events_page)

        default_site = Site.objects.get(is_default_site=True)
        homepage = Page.objects.get(url_path='/home/')
        christmas_page = Page.objects.get(url_path='/home/events/christmas/')

        # with multiple sites, page.url will return full URLs to ensure that
        # they work across sites
        self.assertEqual(homepage.full_url, 'http://localhost/')
        self.assertEqual(homepage.url, 'http://localhost/')
        self.assertEqual(homepage.relative_url(default_site), '/')
        self.assertEqual(homepage.relative_url(events_site), 'http://localhost/')

        self.assertEqual(christmas_page.full_url, 'http://events.example.com/christmas/')
        self.assertEqual(christmas_page.url, 'http://events.example.com/christmas/')
        self.assertEqual(christmas_page.relative_url(default_site), 'http://events.example.com/christmas/')
        self.assertEqual(christmas_page.relative_url(events_site), '/christmas/')

    @override_settings(ROOT_URLCONF='wagtail.tests.non_root_urls')
    def test_urls_with_non_root_urlconf(self):
        default_site = Site.objects.get(is_default_site=True)
        homepage = Page.objects.get(url_path='/home/')
        christmas_page = Page.objects.get(url_path='/home/events/christmas/')

        # Basic installation only has one site configured, so page.url will return local URLs
        self.assertEqual(homepage.full_url, 'http://localhost/site/')
        self.assertEqual(homepage.url, '/site/')
        self.assertEqual(homepage.relative_url(default_site), '/site/')

        self.assertEqual(christmas_page.full_url, 'http://localhost/site/events/christmas/')
        self.assertEqual(christmas_page.url, '/site/events/christmas/')
        self.assertEqual(christmas_page.relative_url(default_site), '/site/events/christmas/')

    def test_request_routing(self):
        homepage = Page.objects.get(url_path='/home/')
        christmas_page = EventPage.objects.get(url_path='/home/events/christmas/')

        request = HttpRequest()
        request.path = '/events/christmas/'
        (found_page, args, kwargs) = homepage.route(request, ['events', 'christmas'])
        self.assertEqual(found_page, christmas_page)

    def test_request_serving(self):
        christmas_page = EventPage.objects.get(url_path='/home/events/christmas/')
        request = HttpRequest()
        response = christmas_page.serve(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['self'], christmas_page)
        used_template = response.resolve_template(response.template_name)
        self.assertEqual(used_template.name, 'tests/event_page.html')

    def test_route_to_unknown_page_returns_404(self):
        homepage = Page.objects.get(url_path='/home/')

        request = HttpRequest()
        request.path = '/events/quinquagesima/'
        with self.assertRaises(Http404):
            homepage.route(request, ['events', 'quinquagesima'])

    def test_route_to_unpublished_page_returns_404(self):
        homepage = Page.objects.get(url_path='/home/')

        request = HttpRequest()
        request.path = '/events/tentative-unpublished-event/'
        with self.assertRaises(Http404):
            homepage.route(request, ['events', 'tentative-unpublished-event'])


class TestServeView(TestCase):
    fixtures = ['test.json']

    def setUp(self):
        # Explicitly clear the cache of site root paths. Normally this would be kept
        # in sync by the Site.save logic, but this is bypassed when the database is
        # rolled back between tests using transactions.
        from django.core.cache import cache
        cache.delete('wagtail_site_root_paths')

        # also need to clear urlresolver caches before/after tests, because we override
        # ROOT_URLCONF in some tests here
        from django.core.urlresolvers import clear_url_caches
        clear_url_caches()

    def tearDown(self):
        from django.core.urlresolvers import clear_url_caches
        clear_url_caches()


    def test_serve(self):
        response = self.client.get('/events/christmas/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'tests/event_page.html')
        christmas_page = EventPage.objects.get(url_path='/home/events/christmas/')
        self.assertEqual(response.context['self'], christmas_page)

        self.assertContains(response, '<h1>Christmas</h1>')
        self.assertContains(response, '<h2>Event</h2>')

    @override_settings(ROOT_URLCONF='wagtail.tests.non_root_urls')
    def test_serve_with_non_root_urls(self):
        response = self.client.get('/site/events/christmas/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'tests/event_page.html')
        christmas_page = EventPage.objects.get(url_path='/home/events/christmas/')
        self.assertEqual(response.context['self'], christmas_page)

        self.assertContains(response, '<h1>Christmas</h1>')
        self.assertContains(response, '<h2>Event</h2>')

    def test_serve_unknown_page_returns_404(self):
        response = self.client.get('/events/quinquagesima/')
        self.assertEqual(response.status_code, 404)

    def test_serve_unpublished_page_returns_404(self):
        response = self.client.get('/events/tentative-unpublished-event/')
        self.assertEqual(response.status_code, 404)

    def test_serve_with_multiple_sites(self):
        events_page = Page.objects.get(url_path='/home/events/')
        Site.objects.create(hostname='events.example.com', root_page=events_page)

        response = self.client.get('/christmas/', HTTP_HOST='events.example.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'tests/event_page.html')
        christmas_page = EventPage.objects.get(url_path='/home/events/christmas/')
        self.assertEqual(response.context['self'], christmas_page)

        self.assertContains(response, '<h1>Christmas</h1>')
        self.assertContains(response, '<h2>Event</h2>')

        # same request to the default host should return a 404
        c = Client()
        response = c.get('/christmas/', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 404)

    def test_serve_with_custom_context(self):
        response = self.client.get('/events/')
        self.assertEqual(response.status_code, 200)

        # should render the whole page
        self.assertContains(response, '<h1>Events</h1>')

        # response should contain data from the custom 'events' context variable
        self.assertContains(response, '<a href="/events/christmas/">Christmas</a>')

    def test_ajax_response(self):
        response = self.client.get('/events/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

        # should only render the content of includes/event_listing.html, not the whole page
        self.assertNotContains(response, '<h1>Events</h1>')
        self.assertContains(response, '<a href="/events/christmas/">Christmas</a>')


    def test_old_style_routing(self):
        """
        Test that route() methods that return an HttpResponse are correctly handled
        """
        with warnings.catch_warnings(record=True) as w:
            response = self.client.get('/old-style-route/')

            # Check that a RemovedInWagtail06Warning has been triggered
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[-1].category, RemovedInWagtail06Warning))
            self.assertTrue("Page.route should return an instance of wagtailcore.url_routing.RouteResult" in str(w[-1].message))

        expected_page = PageWithOldStyleRouteMethod.objects.get(url_path='/home/old-style-route/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['self'], expected_page)
        self.assertEqual(response.templates[0].name, 'tests/simple_page.html')

    def test_before_serve_hook(self):
        response = self.client.get('/events/', HTTP_USER_AGENT='GoogleBot')
        self.assertContains(response, 'bad googlebot no cookie')


class TestStaticSitePaths(TestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=1)

        # For simple tests
        self.home_page = self.root_page.add_child(instance=SimplePage(title="Homepage", slug="home"))
        self.about_page = self.home_page.add_child(instance=SimplePage(title="About us", slug="about"))
        self.contact_page = self.home_page.add_child(instance=SimplePage(title="Contact", slug="contact"))

        # For custom tests
        self.event_index = self.root_page.add_child(instance=EventIndex(title="Events", slug="events"))
        for i in range(20):
            self.event_index.add_child(instance=EventPage(title="Event " + str(i), slug="event" + str(i)))

    def test_local_static_site_paths(self):
        paths = list(self.about_page.get_static_site_paths())

        self.assertEqual(paths, ['/'])

    def test_child_static_site_paths(self):
        paths = list(self.home_page.get_static_site_paths())

        self.assertEqual(paths, ['/', '/about/', '/contact/'])

    def test_custom_static_site_paths(self):
        paths = list(self.event_index.get_static_site_paths())

        # Event index path
        expected_paths = ['/']

        # One path for each page of results
        expected_paths.extend(['/' + str(i + 1) + '/' for i in range(5)])

        # One path for each event page
        expected_paths.extend(['/event' + str(i) + '/' for i in range(20)])

        paths.sort()
        expected_paths.sort()
        self.assertEqual(paths, expected_paths)


class TestMovePage(TestCase):
    fixtures = ['test.json']

    def test_move_page(self):
        about_us_page = SimplePage.objects.get(url_path='/home/about-us/')
        events_index = EventIndex.objects.get(url_path='/home/events/')

        events_index.move(about_us_page, pos='last-child')

        # re-fetch events index to confirm that db fields have been updated
        events_index = EventIndex.objects.get(id=events_index.id)
        self.assertEqual(events_index.url_path, '/home/about-us/events/')
        self.assertEqual(events_index.depth, 4)
        self.assertEqual(events_index.get_parent().id, about_us_page.id)

        # children of events_index should also have been updated
        christmas = events_index.get_children().get(slug='christmas')
        self.assertEqual(christmas.depth, 5)
        self.assertEqual(christmas.url_path, '/home/about-us/events/christmas/')


class TestPrevNextSiblings(TestCase):
    fixtures = ['test.json']

    def test_get_next_siblings(self):
        christmas_event = Page.objects.get(url_path='/home/events/christmas/')
        self.assertTrue(christmas_event.get_next_siblings().filter(url_path='/home/events/final-event/').exists())

    def test_get_next_siblings_inclusive(self):
        christmas_event = Page.objects.get(url_path='/home/events/christmas/')

        # First element must always be the current page
        self.assertEqual(christmas_event.get_next_siblings(inclusive=True).first(), christmas_event)

    def test_get_prev_siblings(self):
        final_event = Page.objects.get(url_path='/home/events/final-event/')
        self.assertTrue(final_event.get_prev_siblings().filter(url_path='/home/events/christmas/').exists())

        # First element must always be the current page
        self.assertEqual(final_event.get_prev_siblings(inclusive=True).first(), final_event)


class TestCopyPage(TestCase):
    fixtures = ['test.json']

    def test_copy_page_copies(self):
        about_us = SimplePage.objects.get(url_path='/home/about-us/')

        # Copy it
        new_about_us = about_us.copy(update_attrs={'title': "New about us", 'slug': 'new-about-us'})

        # Check that new_about_us is correct
        self.assertIsInstance(new_about_us, SimplePage)
        self.assertEqual(new_about_us.title, "New about us")
        self.assertEqual(new_about_us.slug, 'new-about-us')

        # Check that new_about_us is a different page
        self.assertNotEqual(about_us.id, new_about_us.id)

        # Check that the url path was updated
        self.assertEqual(new_about_us.url_path, '/home/new-about-us/')

    def test_copy_page_copies_child_objects(self):
        christmas_event = EventPage.objects.get(url_path='/home/events/christmas/')

        # Copy it
        new_christmas_event = christmas_event.copy(update_attrs={'title': "New christmas event", 'slug': 'new-christmas-event'})

        # Check that the speakers were copied
        self.assertEqual(new_christmas_event.speakers.count(), 1, "Child objects weren't copied")

        # Check that the speakers weren't removed from old page
        self.assertEqual(christmas_event.speakers.count(), 1, "Child objects were removed from the original page")

    def test_copy_page_copies_child_objects_with_nonspecific_class(self):
        # Get chrismas page as Page instead of EventPage
        christmas_event = Page.objects.get(url_path='/home/events/christmas/')

        # Copy it
        new_christmas_event = christmas_event.copy(update_attrs={'title': "New christmas event", 'slug': 'new-christmas-event'})

        # Check that the type of the new page is correct
        self.assertIsInstance(new_christmas_event, EventPage)

        # Check that the speakers were copied
        self.assertEqual(new_christmas_event.speakers.count(), 1, "Child objects weren't copied")

    def test_copy_page_copies_recursively(self):
        events_index = EventIndex.objects.get(url_path='/home/events/')

        # Copy it
        new_events_index = events_index.copy(recursive=True, update_attrs={'title': "New events index", 'slug': 'new-events-index'})

        # Get christmas event
        old_christmas_event = events_index.get_children().filter(slug='christmas').first()
        new_christmas_event = new_events_index.get_children().filter(slug='christmas').first()

        # Check that the event exists in both places
        self.assertNotEqual(new_christmas_event, None, "Child pages weren't copied")
        self.assertNotEqual(old_christmas_event, None, "Child pages were removed from original page")

        # Check that the url path was updated
        self.assertEqual(new_christmas_event.url_path, '/home/new-events-index/christmas/')

    def test_copy_page_copies_recursively_with_child_objects(self):
        events_index = EventIndex.objects.get(url_path='/home/events/')

        # Copy it
        new_events_index = events_index.copy(recursive=True, update_attrs={'title': "New events index", 'slug': 'new-events-index'})

        # Get christmas event
        old_christmas_event = events_index.get_children().filter(slug='christmas').first()
        new_christmas_event = new_events_index.get_children().filter(slug='christmas').first()

        # Check that the speakers were copied
        self.assertEqual(new_christmas_event.specific.speakers.count(), 1, "Child objects weren't copied")

        # Check that the speakers weren't removed from old page
        self.assertEqual(old_christmas_event.specific.speakers.count(), 1, "Child objects were removed from the original page")

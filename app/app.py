from html import escape

import streamlit as st
import streamlit.components.v1 as components

from components import html
from session import (
    backend,
    current_user,
    get_store,
    go_back,
    log_in,
    log_out,
    open_profile,
    pages,
    record_page,
    rehydrate_session,
)
from styles import apply_theme
from views import benchmarks, browse, details, discover, login, profile, watchlist

APP_NAME = "Reelhouse"
WORDMARK = 'Reel<em>house</em>'


def _wrap_page(name, render_fn):
    def wrapped():
        record_page(name)
        render_fn()
    return wrapped


def build_pages():
    pages.clear()
    pages.update({
        "discover": st.Page(_wrap_page("discover", discover.render), title="Discover", url_path="discover", default=True),
        "browse": st.Page(_wrap_page("browse", browse.render), title="Browse", url_path="browse"),
        "watchlist": st.Page(_wrap_page("watchlist", watchlist.render), title="Watchlist", url_path="watchlist"),
        "profile": st.Page(_wrap_page("profile", profile.render), title="Profile", url_path="profile", visibility="hidden"),
        "details": st.Page(_wrap_page("details", details.render), title="Film", url_path="film", visibility="hidden"),
        "benchmarks": st.Page(_wrap_page("benchmarks", benchmarks.render), title="Performance", url_path="performance", visibility="hidden"),
    })


def switch_user():
    users = backend().list_users()
    chosen = st.session_state["switch_user"]
    user_id = users.loc[users["username"] == chosen, "user_id"].iloc[0]
    log_in(backend().get_user(user_id))
    st.session_state.pop("selected_movie", None)
    st.query_params.pop("film", None)


def reset_demo_data():
    get_store().reset()
    st.toast("Demo data restored")


def account_menu(user):
    if not user:
        if st.button("Log in", key="header_login_btn", type="tertiary", icon=":material/login:"):
            st.query_params.clear()
            st.rerun()
        return
    with st.popover("Account", icon=":material/account_circle:"):
        if st.button("Profile", key="header_profile", type="tertiary", icon=":material/person:", use_container_width=True):
            open_profile()
        if st.button("Log out", key="header_logout", type="tertiary", icon=":material/logout:", use_container_width=True):
            log_out()
            st.rerun()


def header(user, is_performance=False):
    with st.container(key="wordmark"):
        user_param = f'?user={escape(user["username"])}' if user and "username" in user else ""
        # href="." navigates to root — Discover is the default page (url_path="", isDefault=True)
        html(f'<a href=".{user_param}" target="_self" class="wordmark-link"><span class="wordmark">{WORDMARK}</span></a>')
    if not is_performance:
        with st.container(key="account"):
            account_menu(user)

    components.html(
        r"""
        <script>
        (function() {
            window.filmGoBack = window.parent.filmGoBack = function(e, targetUrl, pageName) {
                if (e && e.preventDefault) {
                    try { e.preventDefault(); } catch(err) {}
                }
                try {
                    var doc = window.parent.document;
                    if (doc) {
                        var links = doc.querySelectorAll('[data-testid="stTopNavLink"], [data-testid="stTopNav"] a');
                        var matched = null;
                        for (var i = 0; i < links.length; i++) {
                            var el = links[i];
                            var text = (el.textContent || '').trim().toLowerCase();
                            var href = (el.getAttribute('href') || '').toLowerCase();
                            if (pageName === 'browse' && (text.indexOf('browse') !== -1 || href.indexOf('browse') !== -1)) {
                                matched = el;
                                break;
                            }
                            if (pageName === 'watchlist' && (text.indexOf('watchlist') !== -1 || href.indexOf('watchlist') !== -1)) {
                                matched = el;
                                break;
                            }
                            if (pageName === 'discover' && (text.indexOf('discover') !== -1 || href.indexOf('discover') !== -1 || href === '' || href === '.' || href === '/')) {
                                matched = el;
                                break;
                            }
                        }
                        if (!matched && pageName === 'discover') {
                            matched = doc.querySelector('[data-testid="stTopNav"] [data-testid="stTopNavLink"]') ||
                                      doc.querySelector('[class*="st-key-footer_nav"] a');
                        }
                        if (matched) {
                            matched.click();
                            return false;
                        }
                    }
                } catch(err) {}
                try {
                    window.parent.location.href = targetUrl;
                } catch(err) {
                    window.location.href = targetUrl;
                }
                return false;
            };

            // Inject a <style> into the PARENT document head immediately —
            // before React mounts — to prevent stPopoverBody from ever flashing.
            (function injectEarlyStyle() {
                try {
                    var pdoc = window.parent.document;
                    if (!pdoc || pdoc.getElementById('rh-popover-guard')) return;
                    var s = pdoc.createElement('style');
                    s.id = 'rh-popover-guard';
                    s.textContent = [
                        /* Hide ALL popover bodies by default.
                           clip-path is used in addition to visibility because Streamlit mounts
                           [data-testid=\"stPopoverBody\"] as a <body> portal which renders before
                           :has() selectors can suppress it on initial React hydration. */
                        '[data-testid=\"stPopoverBody\"] {',
                        '  opacity: 0 !important;',
                        '  pointer-events: none !important;',
                        '  visibility: hidden !important;',
                        '  clip-path: inset(100%) !important;',
                        '  transition: none !important;',
                        '}',
                        /* Reveal only when Account button is explicitly expanded */
                        'body:has([data-testid=\"stPopoverButton\"][aria-expanded=\"true\"]) [data-testid=\"stPopoverBody\"],',
                        'body:has([data-testid=\"stPopover\"] button[aria-expanded=\"true\"]) [data-testid=\"stPopoverBody\"],',
                        'body:has([class*=\"st-key-account\"] button[aria-expanded=\"true\"]) [data-testid=\"stPopoverBody\"] {',
                        '  opacity: 1 !important;',
                        '  pointer-events: auto !important;',
                        '  visibility: visible !important;',
                        '  clip-path: none !important;',
                        '}',
                        /* Hide account element while still in stMain (before JS moves it) */
                        '[class*=\"st-key-account\"]:not([data-testid=\"stTopNav\"] *):not(.nav-col-right *) {',
                        '  display: none !important;',
                        '}'
                    ].join('\\n');
                    var head = pdoc.head || pdoc.documentElement;
                    head.insertBefore(s, head.firstChild);
                } catch(e) {}
            })();
            function setupNavItems() {
                try {
                    var doc = window.parent.document;
                    if (!doc) return;
                    var nav = doc.querySelector('[data-testid="stTopNav"]');
                    var header = doc.querySelector('[data-testid="stHeader"]');
                    var wm = doc.querySelector('[class*="st-key-wordmark"]');

                    var isPerf = doc.querySelector('.perf-page-marker') !== null ||
                                 (window.parent.location.pathname || '').indexOf('performance') !== -1;

                    if (isPerf) {
                        // Performance page: header must have ONLY the logo
                        var target = nav || (header ? (header.querySelector('[data-testid="stToolbar"] > div') || header) : null);
                        if (target) {
                            var perfNav = target.querySelector('.perf-nav');
                            if (!perfNav) {
                                perfNav = doc.createElement('div');
                                perfNav.className = 'perf-nav';
                                if (nav) nav.innerHTML = '';
                                target.appendChild(perfNav);
                            }
                            if (wm && !perfNav.contains(wm)) {
                                perfNav.innerHTML = '';
                                perfNav.appendChild(wm);
                            }
                        }
                        return;
                    }

                    // For non-performance pages, clean up any leftover perf-nav
                    var strayPerfNav = doc.querySelector('.perf-nav');
                    if (strayPerfNav) {
                        try { strayPerfNav.remove(); } catch(e) {}
                    }

                    if (!nav) return;

                    // Clean up any old nav_back buttons from the header
                    var strayBack = doc.querySelector('[data-testid="stTopNav"] [class*="st-key-nav_back"], [data-testid="stHeader"] [class*="st-key-nav_back"]');
                    if (strayBack) {
                        try { strayBack.remove(); } catch(e) {}
                    }

                    // Check if we need to (re-)structure: columns must exist and contain elements
                    var colLeft   = nav.querySelector('.nav-col-left');
                    var colCenter = nav.querySelector('.nav-col-center');
                    var colRight  = nav.querySelector('.nav-col-right');
                    var acc  = doc.querySelector('[class*="st-key-account"]');
                    var links = nav.querySelectorAll('[data-testid="stTopNavLink"]');

                    // If structure not built or missing elements, build 3 column wrappers
                    var needsRebuild = !colLeft || !colCenter || !colRight ||
                        (acc && !colRight.contains(acc)) ||
                        (wm && !colLeft.contains(wm)) ||
                        (!acc && colRight.querySelector('[class*="st-key-account"]')) ||
                        colCenter.querySelectorAll('[data-testid="stTopNavLink"]').length !== links.length;

                    if (needsRebuild) {
                        // Remove empty Streamlit spacer / sidebar-stub siblings structurally (version-independent)
                        var toolbar = doc.querySelector('[data-testid="stToolbar"]');
                        if (toolbar) {
                            toolbar.style.setProperty('padding', '0', 'important');
                            toolbar.style.setProperty('margin', '0', 'important');
                            Array.prototype.slice.call(toolbar.children).forEach(function(child) {
                                if (child !== nav && !child.contains(nav)) {
                                    try { child.remove(); } catch(e) {}
                                }
                            });
                        }
                        var p = nav.parentElement;
                        if (p && p !== toolbar) {
                            Array.prototype.slice.call(p.children).forEach(function(child) {
                                if (child !== nav && !child.contains(nav)) {
                                    try { child.remove(); } catch(e) {}
                                }
                            });
                        }
                        doc.querySelectorAll('[data-testid="stExpandSidebarButton"]').forEach(function(el) {
                            try { el.remove(); } catch(e) {}
                        });

                        // Expand toolbar parent to full width
                        if (p) {
                            p.style.setProperty('width', '100%', 'important');
                            p.style.setProperty('max-width', '100%', 'important');
                            p.style.setProperty('flex', '1 1 100%', 'important');
                            p.style.setProperty('margin', '0', 'important');
                            p.style.setProperty('padding', '0', 'important');
                        }

                        // Collect page-link items (Discover, Browse, Watchlist) from current nav
                        var linkItems = [];
                        links.forEach(function(link) {
                            var item = link;
                            while (item && item.parentElement !== nav && item.parentElement) {
                                item = item.parentElement;
                                if (item === nav) break;
                            }
                            if (item && item.parentElement === nav && linkItems.indexOf(item) === -1) {
                                linkItems.push(item);
                            }
                        });

                        // Build 3 column wrappers fresh
                        colLeft   = doc.createElement('div');
                        colCenter = doc.createElement('div');
                        colRight  = doc.createElement('div');
                        colLeft.className   = 'nav-col-left';
                        colCenter.className = 'nav-col-center';
                        colRight.className  = 'nav-col-right';

                        // Left: wordmark only
                        if (wm) colLeft.appendChild(wm);

                        // Center: Discover | Browse | Watchlist
                        linkItems.forEach(function(item) { colCenter.appendChild(item); });

                        // Right: Account
                        if (acc) colRight.appendChild(acc);

                        // Clear nav and append columns
                        nav.innerHTML = '';
                        nav.appendChild(colLeft);
                        nav.appendChild(colCenter);
                        nav.appendChild(colRight);
                    }

                    // Wire .film-back-btn clicks
                    var backBtns = doc.querySelectorAll('.film-back-btn');
                    backBtns.forEach(function(btn) {
                        if (btn._hasBackClick) return;
                        btn._hasBackClick = true;
                        btn.addEventListener('click', function(e) {
                            var href = btn.getAttribute('href') || '/';
                            var page = btn.getAttribute('data-page') || 'discover';
                            if (window.parent.filmGoBack) {
                                window.parent.filmGoBack(e, href, page);
                            }
                        });
                    });

                    // Clean up empty element containers left behind in main vertical block
                    var emptyContainers = doc.querySelectorAll('[data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]');
                    emptyContainers.forEach(function(el) {
                        if (!el.querySelector('iframe') && (!el.hasChildNodes() || (el.children.length === 0 && el.textContent.trim() === ''))) {
                            try { el.remove(); } catch(e) {}
                        }
                    });

                } catch(e) {}
                try {
                    var doc = window.parent.document;

                    // Wire wordmark clicks to navigate to Discover (root /) page
                    var wordmarks = doc.querySelectorAll('.wordmark-link, .wordmark');
                    wordmarks.forEach(function(wm) {
                        if (wm._hasNavClick) return;
                        wm._hasNavClick = true;
                        wm.addEventListener('click', function(e) {
                            e.preventDefault();
                            // Discover is the default page — its URL is the root path
                            // Try clicking the Discover nav link first (keeps Streamlit SPA routing)
                            var discNav = doc.querySelector('[data-testid="stTopNav"] [data-testid="stTopNavLink"]');
                            if (!discNav) {
                                discNav = doc.querySelector('[class*="st-key-footer_nav"] a');
                            }
                            if (discNav) {
                                discNav.click();
                            } else {
                                // Fallback: navigate to root preserving user query param
                                var search = window.parent.location.search || '';
                                var userMatch = search.match(/[?&]user=([^&]*)/);
                                var userParam = userMatch ? '?user=' + userMatch[1] : '';
                                window.parent.location.href = '/' + userParam;
                            }
                        });
                    });

                    // Setup genre chevrons if on Discover page
                    var wrap = doc.querySelector('[class*="st-key-genre_strip_wrap"]');
                    if (wrap) {
                        var strip = wrap.querySelector('[data-testid="stHorizontalBlock"]');
                        if (strip) {
                            var prevBtn = wrap.querySelector('.genre-scroll-left');
                            var nextBtn = wrap.querySelector('.genre-scroll-right');

                            if (!prevBtn) {
                                prevBtn = doc.createElement('button');
                                prevBtn.className = 'genre-scroll-btn genre-scroll-left';
                                prevBtn.setAttribute('aria-label', 'Previous genres');
                                prevBtn.setAttribute('type', 'button');
                                prevBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>';
                                prevBtn.addEventListener('click', function(e) {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    strip.scrollBy({ left: -280, behavior: 'smooth' });
                                });
                                wrap.appendChild(prevBtn);
                            }

                            if (!nextBtn) {
                                nextBtn = doc.createElement('button');
                                nextBtn.className = 'genre-scroll-btn genre-scroll-right';
                                nextBtn.setAttribute('aria-label', 'Next genres');
                                nextBtn.setAttribute('type', 'button');
                                nextBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>';
                                nextBtn.addEventListener('click', function(e) {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    strip.scrollBy({ left: 280, behavior: 'smooth' });
                                });
                                wrap.appendChild(nextBtn);
                            }
                        }
                    }

                    // Check broken background images and trigger fallback
                    var artEls = doc.querySelectorAll('.poster-frame .art, .detail-poster .art');
                    artEls.forEach(function(el) {
                        if (el._checked) return;
                        el._checked = true;
                        var style = el.style.backgroundImage || '';
                        var match = style.match(/url\(["']?([^"']+)["']?\)/);
                        if (!match || !match[1]) return;
                        var url = match[1];
                        var img = new Image();
                        img.onerror = function() {
                            el.style.display = 'none';
                            if (el.parentElement) {
                                el.parentElement.classList.add('no-image');
                            }
                            var backdropArt = doc.querySelector('.backdrop .art');
                            if (backdropArt && backdropArt.style.backgroundImage && backdropArt.style.backgroundImage.indexOf(url) !== -1) {
                                backdropArt.style.display = 'none';
                            }
                        };
                        img.src = url;
                    });
                    // Ensure /film page is scrolled to top when accessed
                    try {
                        var search = (window.parent.location.search || '');
                        var path = (window.parent.location.pathname || '');
                        var isFilm = path.indexOf('film') !== -1 || search.indexOf('film=') !== -1 || doc.querySelector('[class*="st-key-detail_block"]') !== null || doc.querySelector('.backdrop') !== null;
                        if (isFilm) {
                            var match = search.match(/[?&]film=([^&]*)/);
                            var currentFilmKey = match ? match[1] : (doc.querySelector('[class*="st-key-detail_block"]') ? 'film_active' : '');
                            if (currentFilmKey && window.parent._lastFilmScrolled !== currentFilmKey) {
                                window.parent._lastFilmScrolled = currentFilmKey;
                                function scrollMainToTop() {
                                    var targets = [
                                        window.parent,
                                        doc.documentElement,
                                        doc.body,
                                        doc.querySelector('.stApp'),
                                        doc.querySelector('[data-testid="stAppViewContainer"]'),
                                        doc.querySelector('[data-testid="stMain"]'),
                                        doc.querySelector('.stMain'),
                                        doc.getElementById('stMain'),
                                        doc.querySelector('main'),
                                        doc.querySelector('section.main'),
                                        doc.querySelector('[data-testid="stMainBlockContainer"]')
                                    ];
                                    targets.forEach(function(t) {
                                        if (!t) return;
                                        try { t.scrollTop = 0; } catch(e) {}
                                        try { if (t.scrollTo) t.scrollTo(0, 0); } catch(e) {}
                                    });
                                    try {
                                        var header = doc.querySelector('[data-testid="stHeader"]');
                                        if (header && header.scrollIntoView) {
                                            header.scrollIntoView({ block: 'start', inline: 'nearest', behavior: 'instant' });
                                        }
                                    } catch(e) {}
                                }
                                scrollMainToTop();
                                if (window.parent.requestAnimationFrame) window.parent.requestAnimationFrame(scrollMainToTop);
                                setTimeout(scrollMainToTop, 20);
                                setTimeout(scrollMainToTop, 80);
                                setTimeout(scrollMainToTop, 200);
                                setTimeout(scrollMainToTop, 400);
                            }
                        } else {
                            window.parent._lastFilmScrolled = null;
                            window.parent._currentFilmId = null;
                        }
                    } catch(e) {}
                } catch(e) {}
            }
            setupNavItems();
            if (window.parent && !window.parent._navItemsObserver) {
                try {
                    var doc = window.parent.document;
                    window.parent._navItemsObserver = new MutationObserver(setupNavItems);
                    window.parent._navItemsObserver.observe(doc.body, { childList: true, subtree: true });
                } catch(e) {}
            }
            setInterval(setupNavItems, 200);
        })();
        </script>
        """,
        height=0,
        width=0,
    )


masthead = header


def footer(is_performance=False):
    html('<div class="footer"><div class="double-rule"></div></div>')
    with st.container(key="site_footer"):
        col_left, col_mid, col_right = st.columns([1, 2, 1], vertical_alignment="center")
        with col_left:
            if is_performance:
                html(f'<span class="wordmark">{WORDMARK}</span>')
            else:
                user = current_user()
                user_param = f'?user={escape(user["username"])}' if user and "username" in user else ""
                html(f'<a href=".{user_param}" target="_self" class="wordmark-link"><span class="wordmark">{WORDMARK}</span></a>')
        with col_mid:
            if not is_performance:
                user = current_user()
                with st.container(key="footer_nav"):
                    if user and all(k in pages for k in ("discover", "browse", "watchlist")):
                        try:
                            st.page_link(pages["discover"], label="DISCOVER")
                            st.page_link(pages["browse"], label="BROWSE")
                            st.page_link(pages["watchlist"], label="WATCHLIST")
                        except Exception:
                            html('<a href=".">DISCOVER</a><a href=".">BROWSE</a><a href=".">WATCHLIST</a>')
                    else:
                        html('<a href=".">DISCOVER</a><a href=".">BROWSE</a><a href=".">WATCHLIST</a>')
        with col_right:
            html('<div class="footer-copy">© 2026 Reelhouse</div>')


def main():
    st.set_page_config(page_title=APP_NAME, page_icon="◆", layout="wide")
    apply_theme()
    try:
        get_store()
    except (OSError, ValueError) as error:
        st.error(f"Couldn't load the film data: {error}")
        st.stop()

    rehydrate_session()
    user = current_user()
    build_pages()

    if user is None:
        guest_pages = [
            st.Page(login.render, title="Welcome", url_path="welcome", default=True, visibility="hidden"),
            pages["benchmarks"],
            st.Page(login.render, title="Discover", url_path="discover", visibility="hidden"),
            st.Page(login.render, title="Browse", url_path="browse", visibility="hidden"),
            st.Page(login.render, title="Watchlist", url_path="watchlist", visibility="hidden"),
            st.Page(login.render, title="Profile", url_path="profile", visibility="hidden"),
            st.Page(login.render, title="Film", url_path="film", visibility="hidden"),
        ]
        navigation = st.navigation(guest_pages, position="top")
        is_perf = (navigation == pages.get("benchmarks"))
        if is_perf:
            masthead(user, is_performance=True)
            navigation.run()
            footer(is_performance=True)
        else:
            navigation.run()
        return

    if user and user.get("username") and st.query_params.get("user") != user["username"]:
        st.query_params["user"] = user["username"]

    navigation = st.navigation(list(pages.values()), position="top")
    is_perf = (navigation == pages.get("benchmarks"))
    masthead(user, is_performance=is_perf)
    navigation.run()
    footer(is_performance=is_perf)


if __name__ == "__main__":
    main()

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
    open_benchmarks,
    open_profile,
    pages,
    record_page,
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


def reset_demo_data():
    get_store().reset()
    st.toast("Demo data restored")


def account_menu(user):
    with st.popover("Account", icon=":material/account_circle:"):
        if st.button("Profile", key="header_profile", type="tertiary", icon=":material/person:", use_container_width=True):
            open_profile()
        if st.button("Performance", key="header_benchmarks", type="tertiary", icon=":material/speed:", use_container_width=True):
            open_benchmarks()
        if st.button("Log out", key="header_logout", type="tertiary", icon=":material/logout:", use_container_width=True):
            log_out()
            st.rerun()


def header(user):
    with st.container(key="nav_back"):
        st.button("← Back", key="nav_back_btn", type="tertiary", on_click=go_back)
    with st.container(key="wordmark"):
        html(f'<span class="wordmark">{WORDMARK}</span>')
    with st.container(key="account"):
        account_menu(user)

    components.html(
        r"""
        <script>
        (function() {
            function setupNavItems() {
                try {
                    var doc = window.parent.document;
                    if (!doc) return;
                    var nav = doc.querySelector('[data-testid="stTopNav"]');
                    if (nav) {
                        var back = doc.querySelector('[class*="st-key-nav_back"]');
                        var wm = doc.querySelector('[class*="st-key-wordmark"]');
                        var acc = doc.querySelector('[class*="st-key-account"]');
                        if (back && nav.firstChild !== back) {
                            nav.insertBefore(back, nav.firstChild);
                        }
                        if (wm && back && back.nextSibling !== wm) {
                            nav.insertBefore(wm, back.nextSibling);
                        }
                        if (acc && !nav.contains(acc)) {
                            nav.appendChild(acc);
                        }
                    }

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


def footer():
    html('<div class="footer"><div class="double-rule"></div></div>')
    with st.container(key="site_footer"):
        col_left, col_mid, col_right = st.columns([1, 2, 1], vertical_alignment="center")
        with col_left:
            html(f'<span class="wordmark">{WORDMARK}</span>')
        with col_mid:
            with st.container(key="footer_nav"):
                st.page_link(pages["discover"], label="DISCOVER")
                st.page_link(pages["browse"], label="BROWSE")
                st.page_link(pages["watchlist"], label="WATCHLIST")
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

    user = current_user()
    if user is None:
        st.navigation([st.Page(login.render, url_path="welcome")], position="hidden").run()
        return

    build_pages()
    navigation = st.navigation(list(pages.values()), position="top")
    masthead(user)
    navigation.run()
    footer()


if __name__ == "__main__":
    main()

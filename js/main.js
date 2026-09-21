/*
  翁彥斌 · 工业设计作品集 v2
  轻量交互：导航滚动效果、移动端菜单、图片灯箱
*/

(function () {
  'use strict';

  /* ───────── 导航滚动 ───────── */
  const nav = document.querySelector('.nav');
  if (nav) {
    const onScroll = () => {
      if (window.scrollY > 40) {
        nav.classList.add('scrolled');
      } else {
        nav.classList.remove('scrolled');
      }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ───────── 移动端菜单 ───────── */
  const menuToggle = document.querySelector('.nav-toggle');
  const mobileMenu = document.querySelector('.mobile-menu');
  const menuLinks = document.querySelectorAll('.mobile-menu a');

  if (menuToggle && mobileMenu) {
    menuToggle.addEventListener('click', () => {
      const isOpen = mobileMenu.classList.contains('open');
      mobileMenu.classList.toggle('open');
      if (nav) nav.classList.toggle('menu-open', !isOpen);
      menuToggle.setAttribute('aria-expanded', String(!isOpen));
      document.body.style.overflow = isOpen ? '' : 'hidden';
    });

    menuLinks.forEach((link) => {
      link.addEventListener('click', () => {
        mobileMenu.classList.remove('open');
        if (nav) nav.classList.remove('menu-open');
        menuToggle.setAttribute('aria-expanded', 'false');
        document.body.style.overflow = '';
      });
    });
  }

  /* ───────── 图片灯箱 ───────── */
  const figures = document.querySelectorAll('.figure img, .project-card-image img, .about-portrait img');
  if (figures.length) {
    figures.forEach((img) => {
      img.style.cursor = 'zoom-in';
      img.addEventListener('click', () => {
        const lightbox = document.createElement('div');
        lightbox.className = 'lightbox';
        lightbox.innerHTML = '<span class="lightbox-close">&times;</span><img src="' + img.src + '" alt="' + (img.alt || '') + '">';
        document.body.appendChild(lightbox);
        document.body.style.overflow = 'hidden';

        const close = () => {
          lightbox.remove();
          document.body.style.overflow = '';
        };

        lightbox.addEventListener('click', close);
        document.addEventListener('keydown', function esc(e) {
          if (e.key === 'Escape') {
            close();
            document.removeEventListener('keydown', esc);
          }
        });
      });
    });
  }
})();

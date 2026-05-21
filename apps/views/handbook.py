from django.views.generic import ListView, DetailView, View
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q, Prefetch, F

from apps.models.handbook import (
    HandbookCategory,
    HandbookSubCategory,
    HandbookItem,
)


class HandbookCategoryListView(ListView):
    model = HandbookCategory
    template_name = 'handbooks/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return (
            HandbookCategory.objects
            .filter(is_active=True)
            .order_by('order', 'title')
        )


class HandbookCategoryDetailView(View):
    """
    Smart view — subcategory bormi?
    - Bor   → subcategory list ko'rsatiladi
    - Yo'q  → to'g'ridan item list ko'rsatiladi
    URL: /handbook/<category_slug>/
    """
    def get(self, request, category_slug):
        category = get_object_or_404(
            HandbookCategory, slug=category_slug, is_active=True
        )

        has_subcategories = HandbookSubCategory.objects.filter(
            category=category, is_active=True
        ).exists()

        if has_subcategories:
            subcategories = (
                HandbookSubCategory.objects
                .filter(category=category, is_active=True)
                .order_by('order', 'title')
            )
            from django.shortcuts import render
            return render(request, 'handbooks/subcategory_list.html', {
                'category': category,
                'subcategories': subcategories,
            })
        else:
            # To'g'ridan itemlar
            items = (
                HandbookItem.objects
                .filter(category=category, is_active=True)
                .order_by('order', 'title')
            )
            search = (request.GET.get('search') or '').strip()
            if search:
                items = items.filter(
                    Q(title__icontains=search) |
                    Q(tags__icontains=search) |
                    Q(short_description__icontains=search)
                )
            from django.shortcuts import render
            return render(request, 'handbooks/item_list.html', {
                'category': category,
                'subcategory': None,
                'items': items,
                'search_query': search,
            })


class HandbookSubCategoryDetailView(View):
    """
    Smart view — subcategory ichida item bormi?
    URL: /handbook/<category_slug>/<subcategory_slug>/
    """
    def get(self, request, category_slug, subcategory_slug):
        category = get_object_or_404(
            HandbookCategory, slug=category_slug, is_active=True
        )
        subcategory = get_object_or_404(
            HandbookSubCategory,
            slug=subcategory_slug,
            category=category,
            is_active=True
        )

        items = (
            HandbookItem.objects
            .filter(subcategory=subcategory, is_active=True)
            .order_by('order', 'title')
        )

        search = (request.GET.get('search') or '').strip()
        if search:
            items = items.filter(
                Q(title__icontains=search) |
                Q(tags__icontains=search) |
                Q(short_description__icontains=search)
            )

        from django.shortcuts import render
        return render(request, 'handbooks/item_list.html', {
            'category': category,
            'subcategory': subcategory,
            'items': items,
            'search_query': search,
        })


class HandbookItemDetailView(DetailView):
    model = HandbookItem
    template_name = 'handbooks/item_detail.html'
    context_object_name = 'item'
    slug_url_kwarg = 'item_slug'

    def get_queryset(self):
        return HandbookItem.objects.filter(
            is_active=True
        ).select_related('subcategory', 'subcategory__category', 'category')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        HandbookItem.objects.filter(pk=obj.pk).update(view_count=F('view_count') + 1)
        obj.refresh_from_db(fields=['view_count'])
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.object

        # Category va subcategory
        context['subcategory'] = item.subcategory
        context['category'] = item.category or (
            item.subcategory.category if item.subcategory else None
        )

        # Related items — subcategory yoki category bo'yicha
        if item.subcategory:
            related = HandbookItem.objects.filter(
                subcategory=item.subcategory, is_active=True
            ).exclude(id=item.id)
        else:
            related = HandbookItem.objects.filter(
                category=item.category, is_active=True
            ).exclude(id=item.id)

        context['related_items'] = related.order_by('order', 'title')[:6]
        return context


class HandbookSearchView(ListView):
    model = HandbookItem
    template_name = 'handbooks/search_results.html'
    context_object_name = 'items'
    paginate_by = 20

    def get_queryset(self):
        query = (self.request.GET.get('q') or '').strip()
        if not query or len(query) < 2:
            return HandbookItem.objects.none()

        return (
            HandbookItem.objects
            .filter(is_active=True)
            .filter(
                Q(title__icontains=query) |
                Q(tags__icontains=query) |
                Q(short_description__icontains=query) |
                Q(description__icontains=query)
            )
            .select_related('subcategory', 'subcategory__category', 'category')
            .order_by('-view_count', 'order', 'title')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['total_results'] = self.get_queryset().count()
        return context
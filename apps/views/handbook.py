from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404
from django.db.models import Q, Prefetch, F

from apps.models.handbook import (
    HandbookCategory,
    HandbookSubCategory,
    HandbookItem,
)


class HandbookCategoryListView(ListView):
    """
    Asosiy Handbook sahifasi - barcha kategoriyalar
    URL: /handbooks/
    """
    model = HandbookCategory
    template_name = 'handbooks/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return (
            HandbookCategory.objects
            .filter(is_active=True)
            .prefetch_related(
                Prefetch(
                    'subcategories',
                    queryset=HandbookSubCategory.objects.filter(is_active=True).order_by('order', 'title')
                )
            )
            .order_by('order', 'title')
        )


class HandbookSubCategoryListView(ListView):
    """
    Bitta kategoriya ichidagi sub-kategoriyalar
    URL: /handbooks/<category_slug>/
    """
    model = HandbookSubCategory
    template_name = 'handbooks/subcategory_list.html'
    context_object_name = 'subcategories'

    def get_queryset(self):
        self.category = get_object_or_404(
            HandbookCategory,
            slug=self.kwargs['category_slug'],
            is_active=True
        )

        return (
            HandbookSubCategory.objects
            .filter(category=self.category, is_active=True)
            .prefetch_related(
                Prefetch(
                    'items',
                    queryset=HandbookItem.objects.filter(is_active=True).order_by('order', 'title')
                )
            )
            .order_by('order', 'title')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        return context


class HandbookItemListView(ListView):
    """
    Sub-kategoriya ichidagi itemlar ro'yxati
    URL: /handbooks/<category_slug>/<subcategory_slug>/
    """
    model = HandbookItem
    template_name = 'handbooks/item_list.html'
    context_object_name = 'items'
    paginate_by = 20

    def get_queryset(self):
        self.category = get_object_or_404(
            HandbookCategory,
            slug=self.kwargs['category_slug'],
            is_active=True
        )
        self.subcategory = get_object_or_404(
            HandbookSubCategory,
            slug=self.kwargs['subcategory_slug'],
            category=self.category,
            is_active=True
        )

        queryset = (
            HandbookItem.objects
            .filter(subcategory=self.subcategory, is_active=True)
            .select_related('subcategory', 'subcategory__category')
        )

        search = (self.request.GET.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(tags__icontains=search) |
                Q(short_description__icontains=search)
            )

        return queryset.order_by('order', 'title')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['subcategory'] = self.subcategory
        context['search_query'] = self.request.GET.get('search', '')
        return context


class HandbookItemDetailView(DetailView):
    """
    Item detail
    URL: /handbooks/<category_slug>/<subcategory_slug>/<item_slug>/
    """
    model = HandbookItem
    template_name = 'handbooks/item_detail.html'
    context_object_name = 'item'
    slug_url_kwarg = 'item_slug'

    def get_queryset(self):
        self.category = get_object_or_404(
            HandbookCategory,
            slug=self.kwargs['category_slug'],
            is_active=True
        )
        self.subcategory = get_object_or_404(
            HandbookSubCategory,
            slug=self.kwargs['subcategory_slug'],
            category=self.category,
            is_active=True
        )

        return (
            HandbookItem.objects
            .filter(subcategory=self.subcategory, is_active=True)
            .select_related('subcategory', 'subcategory__category')
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        HandbookItem.objects.filter(pk=obj.pk).update(view_count=F('view_count') + 1)
        obj.refresh_from_db(fields=['view_count'])

        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['subcategory'] = self.subcategory

        context['related_items'] = (
            HandbookItem.objects
            .filter(subcategory=self.subcategory, is_active=True)
            .exclude(id=self.object.id)
            .order_by('order', 'title')[:6]
        )
        return context


class HandbookSearchView(ListView):
    """
    Global qidiruv
    URL: /handbooks/search/?q=protein
    """
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
            .select_related('subcategory', 'subcategory__category')
            .order_by('-view_count', 'order', 'title')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['total_results'] = self.get_queryset().count()
        return context


class HandbookByCategoryView(ListView):
    model = HandbookItem
    template_name = 'handbooks/category_items.html'
    context_object_name = 'items'
    paginate_by = 24

    def get_queryset(self):
        self.category = get_object_or_404(
            HandbookCategory,
            slug=self.kwargs['category_slug'],
            is_active=True
        )

        return (
            HandbookItem.objects
            .filter(subcategory__category=self.category, is_active=True)
            .select_related('subcategory', 'subcategory__category')
            .order_by('subcategory__order', 'order', 'title')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['subcategories'] = (
            HandbookSubCategory.objects
            .filter(category=self.category, is_active=True)
            .order_by('order', 'title')
        )
        return context

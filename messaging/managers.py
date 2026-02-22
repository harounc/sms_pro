from django.db import models


class CompanyQuerySet(models.QuerySet):
    def for_company(self, company):
        return self.filter(company=company)


class CompanyManager(models.Manager):
    def get_queryset(self):
        return CompanyQuerySet(self.model, using=self._db)

    def for_company(self, company):
        return self.get_queryset().for_company(company)
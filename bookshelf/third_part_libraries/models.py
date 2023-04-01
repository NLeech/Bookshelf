from django.db import models

"""
  `AvtorId` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `FirstName` varchar(99) CHARACTER SET utf8 NOT NULL DEFAULT '',
  `MiddleName` varchar(99) CHARACTER SET utf8 NOT NULL DEFAULT '',
  `LastName` varchar(99) CHARACTER SET utf8 NOT NULL DEFAULT '',
  `NickName` varchar(33) CHARACTER SET utf8 NOT NULL DEFAULT '',
  `uid` int(11) NOT NULL DEFAULT '0',
  `Email` varchar(255) CHARACTER SET utf8 NOT NULL,
  `Homepage` varchar(255) CHARACTER SET utf8 NOT NULL,
  `Gender` char(1) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `MasterId` int(10) NOT NULL DEFAULT '0',
"""


class FlibustaAuthor(models.Model):
    """
    Contains the catalog of authors from https://flibusta.is/sql/
    """
    first_name = models.CharField(max_length=100, blank=True, default='', verbose_name='First name')
    middle_name = models.CharField(max_length=100, blank=True, default='', verbose_name='Middle name')
    last_name = models.CharField(max_length=100, blank=True, default='', verbose_name='Last name')
    nickname = models.CharField(max_length=50, blank=True, default='', verbose_name='Nickname')
    email = models.CharField(max_length=255, blank=True, default='', verbose_name='E-mail')
    homepage = models.CharField(max_length=255, blank=True, default='', verbose_name='First name')
    main_author = models.ForeignKey('self', null=True, blank=True, related_name='different_names',
                                    on_delete=models.CASCADE, verbose_name='Main author')

    def __str__(self):
        return f'({self.id}) {self.last_name} {self.first_name}, {self.middle_name} ({self.main_author})'

# Flibusta library dump description.

The library dump is located at [https://flibusta.is/sql//](https://flibusta.is/sql//) and is updated daily. 
It contains the following files:

lib.libavtorname.sql.gz - contains compressed SQL dump of the `libavtorname` table. 
Table `libavtorname` contains information about authors, including their names, nicknames, email addresses, homepages, and other metadata. 
Each record in the table represents an author or a collective of authors.
The table has the following structure:
```sql
    CREATE TABLE `libavtorname` (
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
      PRIMARY KEY (`AvtorId`),
      KEY `FirstName` (`FirstName`(20)),
      KEY `LastName` (`LastName`(20)),
      KEY `email` (`Email`),
      KEY `Homepage` (`Homepage`),
      KEY `uid` (`uid`),
      KEY `MasterId` (`MasterId`)
    ) ENGINE=MyISAM AUTO_INCREMENT=336014 DEFAULT CHARSET=utf8;
```
Example of a record in the `libavtorname` table:
```sql
INSERT INTO `libavtorname` VALUES (1,'','','Коллектив авторов','',0,'','','',0),(2,'','','Авторский коллектив','',0,'','','',1),(3,'','','Коллектив','',0,'','','',1),(4,'','','Сборник','',0,'','','',1),(5,'','','Сборник статей','',0,'','','',1),(6,'','','Колектив авторів','',0,'','','',1),(7,'','','Разные','',0,'','','',1),(8,'Григол','','Абашидзе','',0,'','','',0),(9,'Гусейн','','Аббасзаде','',0,'','','',0),(10,'Михаил','','Абдрахманов','',0,'','','',0),(11,'Стивен','Уильям','Хокинг','',0,'','','',0),(12,'Эркебек','Сагынбекович','Абдулаев','',0,'','','',0),(13,'Сахиба','','Абдулаева','',0,'','','',135042),(14,'Мади','','Абдулгафаров','',0,'','','',0),(15,'Мансур','','Абдулин','',0,'','','',28924),(16,'Шамшад','Маджитович','Абдуллаев','',0,'','','',0),(17,'Кобо','','Абэ','',0,'','','',0),(18,'Инга','','Абеле','',0,'','','',0),(19,'Пьер','','Абеляр','',0,'','','',0),(20,'Тайша','','Абеляр','',0,'','','',0),(21,'Дмитрий','','Абеляшев','',0,'','','',0),(22,'Кип','','Торн','',0,'','','',222),(23,'Рустам','','Абидов','',0,'','','',0),(24,'Анвар','','Абиджан','',0,'','','',0),(25,'Рафаэль','Викторович','Абоян','',0,'','','',0),(26,'Оксана','Валентиновна','Аболина','',75046,'','','',0),(27,'Н','','Абрамцева','',0,'','','',32161),(28,'Антон','Валерьевич','Абрамкин','',0,'','','',0),(29,'Александр','','Абрамов','',0,'','','',17376),(30,'Сергей','','Абрамов','',0,'','','',0),(31,'Артем','','Абрамов','',0,'','','',0),(32,'Федор','','Абрамов','',0,'','','',27720),(33,'Геннадий','Михайлович','Абрамов','',0,'','','',0),(34,'Я','','Абрамов','',0,'','','',26147),(35,'Михаил','','Абрамов','',0,'','','',26146),(36,'Сергей','','Абрамов','',0,'','','',0),(37,'Всеволод','','Абрамов','',0,'','','',121925),(38,'Исай','','Абрамович','',0,'','','',27763),(39,'Марк','Аркадьевич','Абрамович','',0,'','','',0),(40,'Ольга','Ильтезаровна','Абрамович','',0,'','','',0),(41,'Стелла','','Абрамович','',0,'','','',26148),(42,'Ахмедхан','','Абу-Бакар','',0,'','','',0),(43,'Ильдар','','Абузяро','',0,'','','',108814),(44,'Дмитрий','','Ачасоев','',0,'','','',17994),(45,'Владимир','','Ацюковский','',0,'','','',103502),(46,'Станислав','','Зигуненко','',0,'','','',18891),(47,'Вильгельм','','Адам','',0,'','','',0),(48,'Игорь','Алексеевич','Адамацкий','',0,'','','',0),(49,'Вячеслав','Владимирович','Адамчик','',0,'','','',0),(50,'Виктор','','Адаменко','',0,'','','',226163),(51,'Юрий','','Кириллов','',0,'','','',0),(52,'Аркадий','','Адамов','',0,'','','',17389),(53,'Григорий','Борисович','Адамов','',0,'','','',0),(54,'Алесь','','Адамович','',0,'','http://www.litagent.ru/cliinfoi.asp?KAvt=749','',0),(55,'Нил','Деграсс','Тайсон','',0,'','','',0),(56,'Евгений','','Адамович','',0,'','','',0),(57,'Лидия','','Адамович','',0,'','','',0),(58,'Дуглас','','Адамс','',0,'','','',0),(59,'Джессика','','Адамс','',0,'','','',0),(60,'Генри','','Адамс','',0,'','','',0),(61,'Кайли','','Адамс','',0,'','','',0),(62,'Клифтон','','Адамс','',0,'','','',0),(63,'Памела','','Адамс','',0,'','','',0),(64,'Петер','','Аддамс','',0,'','','',0),(65,'Сэмуэл','','Адамс','',0,'','','',26421),(66,'Джой','','Адамсон','',0,'','','',0),(67,'Петтер','','Аддамс','',0,'','','',64),(68,'Евгений','','Адеев','Lordwolf',0,'','','',0),(69,'Дмитрий','Михайлович','Адеянов','',0,'','','',0),(70,'Альфред','','Адлер','',0,'','','',0),(71,'Элизабет','','Адлер','',0,'','','',0),(72,'Ирэн','','Адлер','',0,'','','',0),(73,'Лор','','Адлер','',0,'','','',61924),(74,'Макс','','Адлер','',0,'','','',0),(75,'Александр','','Адмиральский','',0,'','','',51096),(76,'В','','Адмони','',0,'','','',45841),(77,'Клинтон','Ричард','Докинз','',0,'','','',777),(78,'Валерий','','Аджиев','',0,'','','',0),(79,'Александр','','Афанасьев','Александр В. Маркьянов',0,'','','',0);
```
---
lib.libgenrelist.sql.gz - contains compressed SQL dump of the `libgenrelist` table.
Table `libgenrelist` contains information about book genres, names, codes and metagenres. 
Each record in the table represents a genre of books.
The table has the following structure:
```sql
    CREATE TABLE `libgenrelist` (
      `GenreId` int(10) unsigned NOT NULL AUTO_INCREMENT,
      `GenreCode` varchar(45) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
      `GenreDesc` varchar(99) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
      `GenreMeta` varchar(45) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
      PRIMARY KEY (`GenreId`,`GenreCode`),
      UNIQUE KEY `GenreCode` (`GenreCode`),
      KEY `meta` (`GenreMeta`)
    ) ENGINE=MyISAM AUTO_INCREMENT=298 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
```
Example of a record in the `libgenrelist` table:
```sql
INSERT INTO `libgenrelist` VALUES (1,'sf_history','Альтернативная история','Фантастика'),(2,'sf_action','Боевая фантастика и фэнтези','Фантастика'),(3,'sf_epic','Эпическая фантастика и фэнтези','Фантастика'),(4,'sf_heroic','Героическая фантастика и фэнтези','Фантастика'),(5,'sf_detective','Детективная фантастика','Фантастика'),(6,'sf_cyberpunk','Киберпанк','Фантастика'),(7,'sf_space','Космическая фантастика','Фантастика'),(8,'sf_social','Социально-психологическая фантастика','Фантастика'),(9,'sf_horror','Ужасы','Фантастика'),(10,'sf_humor','Юмористическая фантастика и фэнтези','Фантастика'),(11,'sf_fantasy','Фэнтези','Фантастика'),(12,'sf','Научная фантастика','Фантастика'),(13,'det_classic','Классический детектив','Детективы и триллеры'),(14,'det_police','Полицейский детектив','Детективы и триллеры');
```
---
lib.libseqname.sql.gz - contains compressed SQL dump of the `libseqname` table.
Table `libseqname` contains names of book series.
Each record in the table represents a book series (authors' series or publisher's series).
The table has the following structure:
```sql
    CREATE TABLE `libseqname` (
      `SeqId` int(10) unsigned NOT NULL AUTO_INCREMENT,
      `SeqName` varchar(254) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
      PRIMARY KEY (`SeqId`),
      UNIQUE KEY `SeqName_2` (`SeqName`)
    ) ENGINE=MyISAM AUTO_INCREMENT=107939 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci COMMENT='Список форм (1-100) и названий сериа';
```
Example of a record in the `libseqname` table:
```sql
INSERT INTO `libseqname` VALUES (25341,'Детская литература'),(1,'Романы'),(2,'Повести'),(3,'Рассказы'),(4,'Эссе [Азимов]'),(5,'Поэмы [Пушкин]'),(6,'Стихотворения'),(7,'Публицистика'),(101,'Холм демонов'),(102,'Всадники ниоткуда'),(103,'Magic: The Gathering'),(104,'DOOM'),(105,'Звёзды в ладонях'),(61164,'Мрачная вселенная Фрэнка Миллера'),(112,'Княжеский пир'),(113,'Инспектор Лосев'),(115,'Автостопом по Галактике'),(116,'Дирк Джентли'),(117,'Позитронные роботы'),(8971,'Сборник «Гладь озера в пасмурной мгле»'),(122,'Московская сага'),(123,'Вариант «Бис»'),(124,'Литературные памятники'),(23812,'Ailleurs et demain'),(9906,'The Bride'),(127,'Координаты чудес'),(128,'Винг Алак'),(129,'Короли Иса'),(130,'Приключения Эраста Фандорина'),(131,'Провинцiальный детективъ'),(132,'Жанры [Акунин]'),(133,'Приключения Николаса Фандорина'),(134,'Дата Туташхиа'),(10229,'Greywalker'),(136,'Арвары'),(137,'Сокровища Валькирии'),(140,'След на воде'),(141,'Приключения Лисенка'),(142,'Хроники диверсионного подразделения'),(143,'Миры и междумирье'),(144,'Алтари Келады'),(145,'Пришедшие из мрака'),(146,'Дик Саймон'),(148,'Вокзал времени'),(150,'Артур-полководец'),(151,'Шутт'),(153,'Путь Бога'),(154,'Бригада'),(155,'Тайный сыск царя Гороха'),(156,'Профессиональный оборотень'),(157,'Багдадский вор'),(158,'Моя жена — ведьма'),(159,'Меч без имени'),(160,'Рыжий и Полосатый'),(161,'Джек сумасшедший король'),(162,'Старая крепость'),(163,'Война кукол');
```
---
lib.libbook.sql.gz - contains compressed SQL dump of the `libbook` table.
Table `libbook` contains information about books, including their titles, descriptions, etc. 
Each record in the table represents a book.
The table has the following structure:
```sql
CREATE TABLE `libbook` (
  `BookId` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `FileSize` int(10) unsigned NOT NULL DEFAULT '0',
  `Time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Title` varchar(254) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `Title1` varchar(254) CHARACTER SET utf8 NOT NULL,
  `Lang` char(3) CHARACTER SET utf8 NOT NULL DEFAULT 'ru',
  `LangEx` smallint(6) unsigned NOT NULL DEFAULT '0',
  `SrcLang` char(3) CHARACTER SET utf8 NOT NULL DEFAULT '',
  `FileType` char(4) CHARACTER SET utf8 NOT NULL,
  `Encoding` varchar(32) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `Year` smallint(6) NOT NULL DEFAULT '0',
  `Deleted` char(1) COLLATE utf8_unicode_ci NOT NULL DEFAULT '0',
  `Ver` varchar(8) CHARACTER SET utf8 NOT NULL DEFAULT '',
  `FileAuthor` varchar(64) CHARACTER SET utf8 NOT NULL,
  `N` int(10) unsigned NOT NULL DEFAULT '0',
  `keywords` varchar(255) CHARACTER SET utf8 NOT NULL,
  `md5` binary(32) NOT NULL,
  `Modified` timestamp NOT NULL DEFAULT '2009-11-29 05:00:00',
  `pmd5` char(32) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `InfoCode` tinyint(3) unsigned NOT NULL DEFAULT '0',
  `Pages` int(10) unsigned NOT NULL DEFAULT '0',
  `Chars` int(10) unsigned NOT NULL DEFAULT '0',
  PRIMARY KEY (`BookId`),
  UNIQUE KEY `md5` (`md5`),
  UNIQUE KEY `BookDel` (`Deleted`,`BookId`),
  KEY `Title` (`Title`),
  KEY `Year` (`Year`),
  KEY `Deleted` (`Deleted`),
  KEY `FileType` (`FileType`),
  KEY `Lang` (`Lang`),
  KEY `FileSize` (`FileSize`),
  KEY `FileAuthor` (`FileAuthor`),
  KEY `N` (`N`),
  KEY `Title1` (`Title1`),
  KEY `FileTypeDel` (`Deleted`,`FileType`),
  KEY `LangDel` (`Deleted`,`Lang`)
) ENGINE=MyISAM AUTO_INCREMENT=860973 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
```
Example of a record in the `libbook` table:
```sql
INSERT INTO `libbook` VALUES (1,7162,'2007-06-20 12:24:00','Аида (старая версия файла)','','ru',0,'','fb2','',1111,'1','1.0','rusec',3375,'','fb9ecbecf4b943336ac836202c98fdb3','2026-02-22 06:35:49','',1,0,0),(2,8066,'2007-06-20 12:24:01','Арлекино и Пьеро','','ru',0,'','fb2','',0,'1','1.0','rusec',1510,'','6706f4256630aec18fe2925d0c683bcc','2026-02-22 06:35:49','',1,0,0),(3,29643,'2007-06-20 12:24:01','Барбадару и его Женщина','','ru',0,'','fb2','',0,'1','1.0','rusec',1286,'','94831266f22aef664ac04f75d26438cd','2026-02-22 06:35:49','',1,0,0),(4,16177,'2007-06-20 12:24:01','Дорога','','ru',0,'','fb2','',0,'1','1.0','rusec',3502,'','fc9499d745a9b24a939330d5d09b39fd','2026-02-22 06:35:49','',1,0,0),(5,15022,'2007-06-20 12:24:01','Дождь','','ru',0,'','fb2','',0,'1','1.0','rusec',15240,'','b82d2fe302867012c30fc0161395c4ad','2021-03-07 12:33:12','',1,0,0),(6,9706,'2007-06-20 12:24:01','М','','ru',0,'','fb2','',0,'1','1.0','rusec',1064,'','fab30c339ad1a55dce9026390bc27fe3','2026-02-22 06:35:49','',1,0,0),(7,5972,'2007-06-20 12:24:01','Письмо','','ru',0,'','fb2','',0,'1','1.0','rusec',1574,'','db07a8339a5682eada74fbf33fca731b','2026-02-22 06:35:49','',1,0,0),(8,67165,'2007-06-20 12:24:01','Проект для IGA','','ru',0,'','fb2','',0,'1','1.0','rusec',1060,'','33d487b10a41b43216c8e1e3f90e4657','2026-02-22 06:35:49','',1,0,0),(9,71254,'2007-06-20 12:24:02','Внетелесный опыт','','ru',0,'','fb2','',0,'1','1.0','rusec',733,'','fbbe82be722962e44aaac1dc556c786f','2026-02-18 08:53:55','',1,0,0),(10,7633,'2007-06-20 12:24:02','Душная ночь','','ru',0,'','fb2','',0,'1','1.0','rusec',1710,'','ace2384c5b599700fbf3ef684810aadf','2026-02-22 06:35:49','',1,0,0),(11,803953,'2007-06-20 12:24:02','Искусство наступать на швабру','','ru',0,'','fb2','',0,'1','','rusec',996,'','e197f871a26aaead6d4cc8e15f1f2af5','2026-02-22 06:35:49','',1,0,0),(12,47656,'2007-06-20 12:24:02','Месть призрака','','ru',0,'','fb2','',0,'1','','rusec',908,'','0bb3692392bc2b0091f272269a2acc77','2026-02-22 06:35:49','',1,0,0),(13,53425,'2007-06-20 12:24:02','Недержание истины','','ru',0,'','fb2','',0,'1','','rusec',883,'','216b0c39e000fd38a80842f6666062ab','2026-02-22 06:35:49','',1,0,0),(14,306565,'2007-09-10 02:02:46','Оборотень','','ru',0,'','fb2','',0,'1','','rusec',938,'','0ef4bf21b21c3f9334c8285f59c31d03','2026-02-22 06:35:49','',1,0,0),(15,92787,'2007-06-20 12:24:02','Поэтический побег','','ru',0,'','fb2','',0,'1','','rusec',885,'','a1c8afbbcce6093b76d21d0ab00842c2','2026-02-22 06:35:49','',1,0,0),(16,6014,'2007-06-20 12:24:02','Шекспир в Москве','','ru',0,'','fb2','',0,'1','','rusec',903,'','1f5ff105702494c823ab741ac3eb9631','2026-02-22 06:35:49','',1,0,0),(17,183485,'2007-09-10 02:02:46','Тайны старой усадьбы','','ru',0,'','fb2','',0,'1','','rusec',841,'','efe859994bc7bb4b223be87727500fdd','2026-02-22 06:35:49','',1,0,0),(18,120270,'2007-06-20 12:24:03','Забытые письма','','ru',0,'','fb2','',0,'1','','rusec',870,'','b7b61c716dececb34d501fc268506ed1','2026-02-22 06:35:49','',1,0,0),(19,419705,'2007-09-10 02:02:46','Золотая стрела','','ru',0,'','fb2','',0,'1','','rusec',849,'','f5429965fc28cd3f5edc4b4707d8300c','2026-02-22 06:35:49','',1,0,0),(20,257262,'2007-06-20 12:24:03','Женщина в зеркале','','ru',0,'','fb2','',0,'1','1.0','rusec',431,'','4537df626f015f65cb3e7b6c49469802','2026-02-22 06:35:49','',1,0,0),(21,109910,'2007-06-20 12:24:03','Тайны Сельвента','','ru',0,'','fb2','',0,'1','1.0','rusec',448,'','f8fde6fbde78780c6583d19cce7c7e8e','2026-02-22 06:35:49','',1,0,0),(22,802132,'2007-06-20 12:24:03','Долгая ночь','','ru',0,'','fb2','',0,'1','1.0','rusec',339,'','c1dae70d3711e2c62d4e2b26cfedc339','2026-02-21 14:20:08','',1,0,0),(23,626735,'2007-06-20 12:24:03','Лашарела','','ru',0,'','fb2','',0,'1','1.0','rusec',315,'','7847c470a70d304812be106f6937a34d','2026-02-21 14:20:08','',1,0,0),(24,81783,'2007-06-20 12:24:03','Белка','','ru',0,'','fb2','WINDOWS-1251',0,'1','1.0','rusec',344,'','f28009400d7605e9ddd7df3d383fcd29','2026-02-22 14:12:13','c55d4f1f4d32f0cf7120b17469d57b32',0,40,77233),(25,5995,'2007-06-20 12:24:03','Цветы полевые','','ru',0,'','fb2','WINDOWS-1251',0,'1','1.0','rusec',309,'','de0fa93bdf2950464c5675492dbaeea2','2026-02-22 14:12:13','6c278a55897a22dd166d94c1726ddeb9',0,3,4774);
```
---
lib.libavtor.sql.gz - contains compressed SQL dump of the `libavtor` table.
Table `libavtor` contains information about the relationship between books and authors.
Each record in the table represents a relationship between a book and an author, 
one book can have multiple authors and one author can have multiple books.
The table has the following structure:
```sql
    CREATE TABLE `libavtor` (
      `BookId` int(10) unsigned NOT NULL DEFAULT '0',
      `AvtorId` int(10) unsigned NOT NULL DEFAULT '0',
      `Pos` tinyint(4) unsigned NOT NULL DEFAULT '0',
      PRIMARY KEY (`BookId`,`AvtorId`),
      KEY `iav` (`AvtorId`)
    ) ENGINE=MyISAM DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
```
Example of a record in the `libavtor` table:
```sql
INSERT INTO `libavtor` VALUES (1,59362,1),(413638,19029,1),(9,24445,1),(2,59362,1),(3,59362,1),(4,59362,1),(5,59362,1),(6,59362,1),(7,59362,1),(8,59362,1),(154812,32193,2),(10,24079,1),(11,6409,1),(12,6409,1),(13,6409,1),(14,6409,1),(15,6409,1),(16,6409,1),(17,6409,1),(18,6409,1),(19,6409,1),(20,150363,1),(21,45192,1),(22,8,1),(23,8,1),(24,9,1),(25,9,1),(26,9,1),(27,9,1),(28,9,1),(29,9,1),(30,9,1),(31,9,1),(32,9,1),(33,9,1),(34,9,1),(35,9,1),(36,9,1),(37,9,1),(38,10,1),(39,18532,1),(40,18532,1),(41,18532,1),(42,18532,1),(43,18532,1),(44,18532,1),(45,18532,1),(46,18532,1),(47,18532,1),(48,18532,1),(49,18532,1),(50,18532,1),(51,18532,1),(52,18532,1);
```
---
lib.libgenre.sql.gz - contains compressed SQL dump of the `libgenre` table.
Table `libgenre` contains information about the relationship between books and genres.
Each record in the table represents a relationship between a book and a genre,
one book can belong to multiple genres and one genre can include multiple books.
The table has the following structure:
```sql
CREATE TABLE `libgenre` (
  `Id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `BookId` int(10) unsigned NOT NULL DEFAULT '0',
  `GenreId` int(10) unsigned NOT NULL DEFAULT '0',
  PRIMARY KEY (`Id`),
  UNIQUE KEY `u` (`BookId`,`GenreId`),
  KEY `igenre` (`GenreId`),
  KEY `ibook` (`BookId`)
) ENGINE=MyISAM AUTO_INCREMENT=1631881 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci ROW_FORMAT=DYNAMIC;
```
Example of a record in the `libgenre` table:
```sql
INSERT INTO `libgenre` VALUES (9,9,97),(22,22,61),(23,23,61),(27,27,30),(34,34,30),(38,38,42),(39,39,24),(40,40,24),(41,41,24),(42,42,24),(43,43,24),(44,44,24),(45,45,24),(46,46,24),(47,47,24),(48,48,24),(49,49,24),(50,50,24),(51,51,24),(52,52,24),(53,53,24),(54,54,24),(55,55,24),(56,56,24),(57,57,24),(58,58,24),(59,59,24),(60,60,24),(61,61,24),(62,62,24),(63,63,24),(64,64,24),(66,66,24),(67,67,24),(68,68,24);
```
---
lib.libgenre.sql.gz - contains compressed SQL dump of the `libgenre` table.
Table `libgenre` contains information about the relationship between books and genres.
Each record in the table represents a relationship between a book and a genre,
one book can belong to multiple genres and one genre can include multiple books.
The table has the following structure:
```sql
CREATE TABLE `libgenre` (
  `Id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `BookId` int(10) unsigned NOT NULL DEFAULT '0',
  `GenreId` int(10) unsigned NOT NULL DEFAULT '0',
  PRIMARY KEY (`Id`),
  UNIQUE KEY `u` (`BookId`,`GenreId`),
  KEY `igenre` (`GenreId`),
  KEY `ibook` (`BookId`)
) ENGINE=MyISAM AUTO_INCREMENT=1631881 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci ROW_FORMAT=DYNAMIC;
```
Example of a record in the `libgenre` table:
```sql
INSERT INTO `libgenre` VALUES (9,9,97),(22,22,61),(23,23,61),(27,27,30),(34,34,30),(38,38,42),(39,39,24),(40,40,24),(41,41,24),(42,42,24),(43,43,24),(44,44,24),(45,45,24),(46,46,24),(47,47,24),(48,48,24),(49,49,24),(50,50,24),(51,51,24),(52,52,24),(53,53,24),(54,54,24),(55,55,24),(56,56,24),(57,57,24),(58,58,24),(59,59,24),(60,60,24),(61,61,24),(62,62,24),(63,63,24),(64,64,24),(66,66,24),(67,67,24),(68,68,24),(69,69,24),(70,70,24),(71,71,24),(72,72,24),(73,73,24),(74,74,24),(75,75,24);
```
---
lib.libjoinedbooks.sql.gz - contains compressed SQL dump of the `libjoinedbooks` table.
Table `libjoinedbooks` contains information about the book replacement, 
which is used when a book is removed from the library and replaced by new/updated version of the same book.
Each record in the table represents a relationship between the old book and the new book.
The table has the following structure:
```sql
CREATE TABLE `libjoinedbooks` (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `Time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `BadId` int(11) NOT NULL DEFAULT '0',
  `GoodId` int(11) NOT NULL DEFAULT '0',
  `realId` int(11) DEFAULT NULL,
  PRIMARY KEY (`Id`),
  UNIQUE KEY `BadId` (`BadId`),
  KEY `Time` (`Time`),
  KEY `GoodId` (`GoodId`),
  KEY `realId` (`realId`)
) ENGINE=MyISAM AUTO_INCREMENT=157729 DEFAULT CHARSET=utf8;
```
Example of a record in the `libjoinedbooks` table:
```sql
INSERT INTO `libjoinedbooks` VALUES (1,'2008-03-28 11:25:16',17518,98113,98113),(2,'2008-03-28 11:50:29',36466,98120,98580),(3,'2008-03-28 14:36:09',66196,98151,98151),(4,'2008-03-28 14:36:32',7348,98152,98152),(5,'2008-03-28 14:36:38',8157,98156,98156),(6,'2008-03-28 14:36:56',79140,98161,98161),(7,'2008-03-28 14:37:05',29953,98164,98164),(8,'2008-03-28 14:37:18',29964,98165,98165),(9,'2008-03-28 14:39:02',68365,98167,98167),(10,'2008-03-28 14:39:27',69898,98168,98168),(11,'2008-03-28 14:40:22',68731,98169,98169),(12,'2008-03-28 14:40:36',42663,98170,98170),(13,'2008-03-28 14:40:40',45318,98171,98171),(14,'2008-03-28 14:40:46',98114,98172,98172),(15,'2008-03-28 14:40:49',45336,98173,98173),(16,'2008-03-28 14:41:08',80362,98174,98174),(17,'2008-03-28 14:41:32',78695,98175,98175),(18,'2008-03-28 14:47:00',98179,66005,66005),(19,'2008-03-28 14:49:12',98180,66059,489028),(20,'2008-03-28 14:49:34',6601,98183,98183);
```

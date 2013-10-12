
-- Database for the bits system
-- Recomendations: make three users
-- bits_ro    : (php)    privileges SELECT
-- bits       : (python) privileges SELECT INSERT UPDATE DELETE
-- bits_admin : (admin)  privileges SELECT INSERT UPDATE DELETE ALTER CREATE DROP
-- the users must have different passwords

use bitsdb; -- database name

-- Temperature samples are stored here
create table if not exists Temperature
(
  `timestamp` datetime not null, -- When the sample was taken
  `sensor` tinyint(2) not null,  -- From which sensor it comes from
  `value` float not null,        -- Actual temperature sample
  primary key(`timestamp`, `sensor`)
) ENGINE=InnoDB;

-- Users are stored here, including admins
create table if not exists Users
(
  `userid` int(10) primary key auto_increment,            -- User id
  `username` varchar(20) collate utf8_bin not null unique,-- User name
  `password` varchar(40) collate utf8_bin not null,       -- SHA1 of password
  `accesslevel` varchar(15) ascii not null
   -- l=Can login
   -- m=Can send messages
   -- a=Is admin
) ENGINE=InnoDB default charset=utf8 collate=utf8_bin auto_increment=1;

-- Users logged into the website. Logout==NULL means loged in now, else is historic data
create table if not exists WebsiteLogin
(
  `userid` int(10) references Users(`userid`) on delete cascade on update cascade,
  `login` datetime not null,      -- When person logged into the website
  `logout` datetime default null, -- When person logged out
  primary key(`userid`, `login`)
) ENGINE=InnoDB;

-- Sede status is stored here (only open, closed)
create table if not exists Status
(
  `timestamp` datetime primary key,  -- When status change happened
  `value` tinyint(1) not null,        -- 1=Open 0=Closed
  `modifiedby` tinyint(1) not null   -- 0=Bits 1=From the website
) ENGINE=InnoDB;

-- Users in sede. Logout==NULL means user is in sede, logout!=NULL is historic data
create table if not exists Presence
(
  `userid` int(10) references Users(`userid`) on delete cascade on update cascade,
  `login` datetime not null,      -- When person entered
  `logout` datetime default null, -- When person left
  primary key(`userid`, `login`)
) ENGINE=InnoDB;

-- Messages are stored here
create table if not exists Message
(
  `userid` int(10) references Users(`userid`) on delete cascade on update cascade,
  `timestamp` datetime not null,                    -- When message was sent
  `message` varchar(160) collate utf8_bin not null, -- Message text
  primary key (`userid`, `timestamp`)
) ENGINE=InnoDB default charset=utf8 collate=utf8_bin;

-- Add admins to the database (these are just test users, should not end up in the db)
--insert into Users (`userid`, `username`, `password`, `accesslevel`) values
--(0, 'beta4', 'c8fed00eb2e87f1cee8e90ebbe870c190ac3848c', 'lma');
--(0, 'otacon22', 'c8fed00eb2e87f1cee8e90ebbe870c190ac3848c', 'lma');

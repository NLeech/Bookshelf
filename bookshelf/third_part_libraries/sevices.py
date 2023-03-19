from io import StringIO
import re


class FlibustaInterface:
    """
    Interface for the Flibusta library.
    Gets database dump from Flibusta and stores it to the database.
    """

    def _get_authors_dump(self) -> StringIO:
        """
        Get database dump with authors from flibusta site
        :return: raw SQL dump
        """
        pass

    def _parse_authors_dump(self, dump: StringIO):
        # Split the backup file into individual SQL statements
        sql_statements = re.split(r';[\n\r]+', dump)

        for sql in sql_statements:
            # Ignore comments and empty statements
            if sql.startswith('--') or not sql.strip():
                continue

            # Extract the column names and values from INSERT INTO statements
            match = re.search(r"INSERT INTO `(\w+)` \((.*)\) VALUES \((.*)\)", sql)
            if match:
                table_name = match.group(1)
                column_names = match.group(2).split(',')
                values = match.group(3).split(',')
                data = dict(zip(column_names, values))
                print(f"Data for table {table_name}: {data}")



"""empty message

Revision ID: 510b23c2ceef
Revises: 23c0c62383bb
Create Date: 2016-03-10 15:36:11.079183

"""

# revision identifiers, used by Alembic.
revision = '510b23c2ceef'
down_revision = '23c0c62383bb'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('farmer') as batch_op:
        batch_op.drop_column('btc_addr')
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('farmer', sa.Column('btc_addr', sa.VARCHAR(length=35), nullable=True))
    ### end Alembic commands ###

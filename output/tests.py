from drain import data
from drain.data import FromSQL
from drain.step import Step
from drain.aggregation import SpacetimeAggregation
from drain.aggregate import Count, Aggregate

import pandas as pd
import logging

# TODO: make this more efficient by not including unnecessary address columns
tests = FromSQL(table='output.tests', parse_dates=['sample_date'], 
        target=True)
kids = FromSQL(table='output.kids', parse_dates=['date_of_birth', 
        'first_bll6_sample_date', 'first_bll10_sample_date', 
        'first_sample_date', 'last_sample_date'],
        to_str=['first_name', 'last_name'], target=True)
addresses = FromSQL(table='output.addresses', target=True)

def censor(tests, date, delta):
    logging.info('Censoring tests %s %s' % (date, delta))
    tests = data.date_select(tests, 'sample_date', date, delta)
    tests = data.date_censor(tests.copy(), 
            {'first_bll6_sample_date':[], 'first_bll10_sample_date':[]}, date)
    return tests

def revise(tests, kids, date):
    """
    Efficiently revise tests by only recalculating those aggregates that could have changed
    Does not modify the dataframe tests
    """
    logging.info('Revising tests %s' % date)
    tests = data.date_select(tests, 'sample_date', date, 'all')
    kids = data.date_select(kids, 'first_sample_date', date, 'all')

    to_revise = kids.last_sample_date >= date
    # drop the columns that need to be revised
    kids_to_revise = kids[to_revise].drop(
            ['max_bll', 'mean_bll', 'last_sample_date', 
            'address_count', 'test_count'], axis=1)
     
    tests_to_revise = tests[tests.kid_id.isin(kids_to_revise.kid_id)]

    # find last sample
    last_idx = tests_to_revise.groupby('kid_id')['age'].idxmax()
    last_tests = tests_to_revise.ix[last_idx]
    last_tests = last_tests[['kid_id', 'sample_date']].rename(
            columns={'sample_date':'last_sample_date'})
    kids_to_revise = kids_to_revise.merge(last_tests, on='kid_id')

    # count addresses and tests
    counts = tests_to_revise.groupby('kid_id').aggregate(
            {'bll': ['max', 'mean'], 'address_id':'nunique', 
             'test_id':'count'})
    counts.rename(columns={('bll', 'max'):'max_bll', 
            ('bll','mean'):'mean', 'address_id':'address_count', 
            'test_id':'test_count'}, inplace=True) 
    df = df.merge(counts, left_on='kid_id', right_index=True)

    return pd.concat((kids[~to_revise], kids_to_revise))


class TestsAggregation(SpacetimeAggregation):
    def __init__(self, spacedeltas, dates, **kwargs):
        SpacetimeAggregation.__init__(self,
            spacedeltas=spacedeltas, dates=dates, prefix='tests',
            date_column='sample_date', **kwargs)

        if not self.parallel:
            self.inputs = [tests]

        self.revised_data = {}
            
    # TODO add tests as input and do censoring and feature generation on given thresholds (a parameter)

    def get_data(self, date, delta):
        if date in self.revised_data:
            revised = self.revised_data[date]
        else:
            revised = revise(self.inputs[0].get_result(), date)
            self.revised_data[date] = revised

        return censor(revised, date, delta)

    def get_aggregates(self, date, delta):
        bll6 = lambda t: t.bll > 5
        bll10 = lambda t: t.bll > 9

        bll6_kid_id = lambda t: t.kid_id.where(t.first_bll6_sample_date.notnull())
        bll10_kid_id = lambda t: t.kid_id.where(t.first_bll10_sample_date.notnull())

        bll_ever_count = Aggregate(
                [bll6_kid_id, bll10_kid_id], 'nunique', 
                name=['kid_bll6_ever_count', 'kid_bll10_ever_count'], 
                fname=False)

        kid_count = Aggregate('kid_id', 'nunique', name='kid_count')
        family_count = Aggregate('last_name', 'nunique', 
                name='family_count')

        aggregates = [
            Count(),
            Aggregate('bll', ['mean', 'median', 'max', 'min', 'std']),
            # TODO: include mean_bll in output.kids and in censor()
#            Aggregate('kid_mean_bll', ['mean', 'median', 'max', 'min', 'std']),
            Aggregate('max_bll', ['mean', 'median', 'max', 'min', 'std']),
            Count([bll6, bll10], name=['bll6', 'bll10'], prop=True),
            bll_ever_count,
            bll_ever_count / kid_count,
            kid_count

#            Aggregate('kid_first_ebll_age', ['mean', 'median']),
#            Aggregate('kid_first_sample_age', ['mean', 'median']),

        ]

        return aggregates

        # use a method because in a loop lambdas' references to threshold won't stick!
    def get_ebll_aggregates(self, threshold):
        ebll_test = lambda t: (t.test_bll > threshold)
        ebll_kid_ids = lambda t: t.kid_id.where(t.test_bll > threshold)

        bll = 'ebll%s' % threshold
        return [
            Aggregate(ebll_test, ['any', 'test'], name=bll),
            Aggregate(lambda t: t.kid_last_name.where(t.test_bll > threshold),
                'nunique', 'family_' + bll),
            Count('first_%s' % bll, name=bll+'_here'),
            Aggregate(lambda t: t.kid_id.where(t.kid_max_bll > threshold),
                'nunique', 'kid_' + bll + '_ever'),
            Aggregate(lambda t: t.kid_id.where(
                    t['kid_first_%s_date' % bll] > t.sample_date),
                'nunique', 'kid_' + bll + '_future'),
        ]

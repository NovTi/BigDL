#
# Copyright 2016 The BigDL Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import tempfile
import os.path
import pytest
from unittest import TestCase
import shutil

import bigdl.orca.data
import bigdl.orca.data.pandas
from bigdl.orca import OrcaContext
from bigdl.dllib.nncontext import *
from bigdl.orca.data.image import write_tfrecord, read_tfrecord
from bigdl.orca.data.utils import *
from bigdl.orca.data.transformer import *


class TestXShardsSparkBackend(TestCase):
    def setup_method(self, method):
        self.resource_path = os.path.join(os.path.split(__file__)[0], "../resources")

    def test_header_and_names(self):
        file_path = os.path.join(self.resource_path, "orca/data/csv")
        # Default header="infer"
        data_shard = bigdl.orca.data.pandas.read_csv(file_path)
        data = data_shard.collect()
        assert len(data) == 2, "number of shard should be 2"
        df = data[0]
        assert "location" in df.columns
        file_path = os.path.join(self.resource_path, "orca/data/no_header.csv")
        # No header, default to be '0','1','2'
        data_shard = bigdl.orca.data.pandas.read_csv(file_path, header=None)
        df2 = data_shard.collect()[0]
        assert '0' in df2.columns and '2' in df2.columns
        # Specify names as header
        data_shard = bigdl.orca.data.pandas.read_csv(
            file_path, header=None, names=["ID", "sale_price", "location"])
        df3 = data_shard.collect()[0]
        assert "sale_price" in df3.columns

    def test_read_invalid_path(self):
        file_path = os.path.join(self.resource_path, "abc")
        with self.assertRaises(Exception) as context:
            xshards = bigdl.orca.data.pandas.read_csv(file_path)
        # This error is raised by pyspark.sql.utils.AnalysisException
        self.assertTrue('Path does not exist' in str(context.exception))

    def test_read_json(self):
        file_path = os.path.join(self.resource_path, "orca/data/json")
        data_shard = bigdl.orca.data.pandas.read_json(file_path)
        data = data_shard.collect()
        df = data[0]
        assert "timestamp" in df.columns and "value" in df.columns
        data_shard = bigdl.orca.data.pandas.read_json(file_path, names=["time", "value"])
        data = data_shard.collect()
        df2 = data[0]
        assert "time" in df2.columns and "value" in df2.columns
        data_shard = bigdl.orca.data.pandas.read_json(file_path, usecols=[0])
        data = data_shard.collect()
        df3 = data[0]
        assert "timestamp" in df3.columns and "value" not in df3.columns
        data_shard = bigdl.orca.data.pandas.read_json(file_path, dtype={"value": "float"})
        data = data_shard.collect()
        df4 = data[0]
        assert df4.value.dtype == "float64"

    def test_read_parquet(self):
        file_path = os.path.join(self.resource_path, "orca/data/csv")
        sc = init_nncontext()
        from pyspark.sql.functions import col
        spark = OrcaContext.get_spark_session()
        df = spark.read.csv(file_path, header=True)
        df = df.withColumn('sale_price', col('sale_price').cast('int'))
        temp = tempfile.mkdtemp()
        df.write.parquet(os.path.join(temp, "test_parquet"))
        data_shard2 = bigdl.orca.data.pandas.read_parquet(os.path.join(temp, "test_parquet"))
        assert data_shard2.num_partitions() == 2, "number of shard should be 2"
        data = data_shard2.collect()
        df = data[0]
        assert "location" in df.columns

        data_shard2 = bigdl.orca.data.pandas.read_parquet(os.path.join(temp, "test_parquet"),
                                                          columns=['ID', 'sale_price'])
        data = data_shard2.collect()
        df = data[0]
        assert len(df.columns) == 2

        from pyspark.sql.types import StructType, StructField, IntegerType, StringType
        schema = StructType([StructField("ID", StringType(), True),
                             StructField("sale_price", IntegerType(), True),
                             StructField("location", StringType(), True)])
        data_shard3 = bigdl.orca.data.pandas.read_parquet(os.path.join(temp, "test_parquet"),
                                                          columns=['ID', 'sale_price'],
                                                          schema=schema)
        data = data_shard3.collect()
        df = data[0]
        assert str(df['sale_price'].dtype) == 'int64'

        shutil.rmtree(temp)

    def test_write_read_imagenet(self):
        raw_data = os.path.join(self.resource_path, "imagenet_to_tfrecord")
        temp_dir = tempfile.mkdtemp()
        try:
            write_tfrecord(format="imagenet", imagenet_path=raw_data, output_path=temp_dir)
            data_dir = os.path.join(temp_dir, "train")
            train_dataset = read_tfrecord(format="imagenet", path=data_dir, is_training=True)
            train_dataset.take(1)
        finally:
            shutil.rmtree(temp_dir)

    def test_read_large_csv(self):
        file_path = os.path.join(self.resource_path, "orca/data/10010.csv")
        data_shard = bigdl.orca.data.pandas.read_csv(file_path)
        res = data_shard.collect()
        assert len(res[0]) == 10009, "number of records should be 10009"


if __name__ == "__main__":
    pytest.main([__file__])